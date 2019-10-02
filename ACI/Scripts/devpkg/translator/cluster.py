'''
Created on Oct 19, 2013

@author: feliu
'''

from translator.base.dmobject import DMObject
from translator.base.dmlist import DMList
from translator.base.simpletype import SimpleType
from translator.base.dmboolean import DMBoolean
from translator.base.compositetype import CompositeType
from translator.structured_cli import StructuredCommand
from utils.util import normalize_param_dict, ifcize_param_dict, query_asa
from asaio.cli_interaction import CLIInteraction
from translator.state_type import Type, State
import utils.util as util
import re

class ClusterConfig(DMObject):
    '''
    This class represents the holder of all cluster configuration.
    '''

    def __init__(self):
        DMObject.__init__(self, ClusterConfig.__name__)
        self.register_child(ClusterRole())
        self.register_child(DMList('pool_config', PoolConfig, asa_key='ip local pool'))
        self.register_child(BootstrapConfig())
        self.register_child(ClusterMtu())

    @staticmethod
    def is_cluster_master():
        # By default the role is not set to master unless it is explicitly declared
        return ClusterConfig.is_master if hasattr(ClusterConfig, 'is_master') else False

    @staticmethod
    def set_cluster_master(is_master):
        # Set cluster role. Set to 'True' if master, otherwise 'False'.
        ClusterConfig.is_master = is_master

    @staticmethod
    def get_fault_path():
        root = util.get_config_root_key('')
        fault_path = []
        if not root:
            fault_path.append(root)
        fault_path.append((4, 'ClusterConfig', ''))
        return fault_path

    @staticmethod
    def get_cluster_check_cli(configuration):
        role = ClusterConfig.get_cluster_role(configuration)
        if role:
            ClusterConfig.set_cluster_master(role == 'master')
            return 'show cluster info'

    @staticmethod
    def get_cluster_role(configuration):
        if isinstance(configuration, dict):
            for key, val in dict(configuration).iteritems():
                if key[1] == 'cluster_role':
                    return val['value']
                else:
                    role = ClusterConfig.get_cluster_role(val['value'])
                    if role:
                        return role

    @staticmethod
    def get_health(device, configuration):
        """
        @param device: dictionary to identify the device
        @param configuration: IFC configuration parameter
        @return the health tuple for cluster, (path, integer), or None if thing is fine or not not able to reach the device
        """
        cli = ClusterConfig.get_cluster_check_cli(configuration)
        if not cli:
            return None

        response = query_asa(device, cli)[0]
        if ClusterConfig.is_cluster_master():
            p = re.compile('.*This is .* in state MASTER.*', re.DOTALL)
        else: # Must be slave setup
            p = re.compile('.*This is .* in state SLAVE.*', re.DOTALL)
        # If cluster is in MASTER or SLAVE role now, then we don't return any Fault
        return (ClusterConfig.get_fault_path(), 100 if p.match(response) else 0)

class ClusterRole(DMObject):
    '''
    This class represents the cluster role configuration.
    '''
    def __init__(self):
        DMObject.__init__(self, 'cluster_role')

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate the cluster role configuration
        '''
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        config = util.normalize_param_dict(delta_ifc_cfg_value['value'])
        ClusterConfig.is_master = str(config).lower() == 'master'

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        cli = self.get_cli()
        if cli:
            asa_cfg_list.append(CLIInteraction(command=cli, response_parser=cluster_response_parser))

    def get_cli(self):
        if not hasattr(self, 'delta_ifc_key'):
            return ''
        # setup cluster master or slave, make sure cluster interface-mode is set.
        return 'cluster interface-mode spanned force'


class PoolConfig(SimpleType):
    '''
    This class represents the IP local pool configuration.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template = "ip local pool %(pool_name)s %(start_ip)s-%(end_ip)s",
                            response_parser = cluster_response_parser)

    def get_cli(self):
        '''Generate the CLI for this single cluster ip config.
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        mask = config.get('mask')
        result = SimpleType.get_cli(self)
        if mask:
            result += ' mask ' + mask
        return ' '.join(result.split())

    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.asa_gen_template % value

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional parameter
        '''
        # The names in template: "ip local pool %(pool_name)s %(start_ip)s-%(end_ip)s"
        names = ['pool_name', 'start_ip', 'end_ip']

        # s is the regular expression for parsing above CLI
        s = 'ip local pool (\S+) (\S+)-(\S+)'

        pattern = re.compile(s)
        m = pattern.match(cli.strip())

        result = {}
        for pos, name in enumerate(names, 1):
            result[name] = m.group(pos)
        result = ifcize_param_dict(result)

        'Take care of the optional parameters'
        tokens = cli.split()

        # If the number of tokens > 6, it has mask option:
        # CLI format: 'ip local pool %(pool_name)s %(start_ip)s-%(end_ip)s mask <mask>'
        if len(tokens) > 6:
            option = tokens[6:]
            if len(option) > 0:
                result[(Type.PARAM, 'mask', '')] = {'state': State.NOCHANGE, 'value': ''}
                result[Type.PARAM, 'mask', '']['value'] = option[0]
        return result

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, interfaces = None):
        '''Generate ASA configuration from IFC configuration delta.
        @see DMObject.ifc2asa for parameter details
        '''
        if not self.has_ifc_delta_cfg():
            return
        action = self.get_action()
        if action == State.NOCHANGE:
            return

        if action == State.DESTROY and self.is_removable:
            self.generate_cli(no_asa_cfg_stack, 'no ' + self.get_cli())
        else:
            self.generate_cli(asa_cfg_list, self.get_cli())
        # apply the pool to the management interface
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        intf = self.get_top().get_mgmt_interface()
        if not intf:
            # default management interface: m0/0
            intf = 'm0/0'
        attr = self.get_mgmt_intf_attributes(intf)
        if attr == None:
            return
        clii = CLIInteraction(mode_command='interface ' + util.normalize_interface_name(intf),
            command='ip address ' + attr['ip'] + ' ' + attr['mask'] + ' cluster-pool ' + value['pool_name'],
            response_parser=cluster_response_parser)
        asa_cfg_list.append(clii)
        SimpleType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def get_mgmt_intf_attributes(self, intf):
        '''
        @param intf - the name of the mgmt interface on the specified device
        '''
        result = self.query_asa('show run int ' + intf + ' | grep ip address')
        if result == None:
            return
        # result format: ip address <ip> <mask> ...
        attr_list = result.split()
        return {'ip':attr_list[2], 'mask':attr_list[3]}


class BootstrapConfig(CompositeType):
    '''
    This class represents the cluster bootstrap configuration.
    '''

    def __init__(self):
        CompositeType.__init__(self, ifc_key = 'bootstrap_config',
                               asa_key = 'cluster group',
                               asa_gen_template = "cluster group %(group_name)s",
                               response_parser = cluster_response_parser)
        self.register_child(ConnectionRebalance())
        self.register_child(ConsoleReplicate())
        self.register_child(HealthCheck())
        self.register_child(SecretKey())
        self.register_child(LocalUnit())
        self.register_child(Priority())
        self.register_child(Clacp())
        self.register_child(ClusterInterface())
        self.register_child(EnableCluster())

    def get_translator(self, cli):
        '''Find the DMObject within this DMOBject that can translate a CLI
        @param cli: CLI
        @return:  the DMObject that can translate the cli
        '''
        if self.is_my_cli(cli):
            return self

    def diff_ifc_asa(self, cli):
        'Take care of the case where the field is empty, which means delete operation here'
        if self.get_cli().strip() == self.asa_key and cli != self.asa_key and self.has_ifc_delta_cfg():
            del self.delta_ifc_key
            del self.delta_ifc_cfg_value
        return CompositeType.diff_ifc_asa(self, cli)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        @see DMObject.ifc2asa for parameter details
        '''

        CompositeType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)
        if not self.has_ifc_delta_cfg():
            return
        action = self.get_action()
        if action == State.NOCHANGE:
            return

        if action == State.DESTROY and self.is_removable:
            # when removing cluster group, disable the cluster first
            no_asa_cfg_stack.append(CLIInteraction('no enable', mode_command=self.get_cli()))

    def get_cli(self):
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        if value == {}:
            return self.asa_key

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())

    def is_the_same_cli(self, cli):
        'Override default implementation to compare sub-commands with those of the children'
        'check the sub-commands, order is not important'
        return cli.command == self.get_cli() and set(cli.sub_commands) == set(self.get_sub_commands())

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        'Override the default implementation to let the children sharing the dictionary'
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value

        for child in self.children.values():
            if child.ifc_key in ('cluster_interface', 'clacp'):
                for (t, key, instance), v in self.delta_ifc_cfg_value['value'].iteritems():
                    if (key == child.ifc_key):
                        value = self.delta_ifc_cfg_value['value'].get((Type.FOLDER, child.ifc_key, instance))
                        child.populate_model(delta_ifc_key, value)
            else:
                child.populate_model(delta_ifc_key, delta_ifc_cfg_value)


class ConnectionRebalance(SimpleType):
    'Translator for connection re-balance sub-command'
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'conn_rebalance',
                            asa_key = 'conn-rebalance',
                            asa_mode_template = 'cluster group %(group_name)s',
                            asa_gen_template = 'conn-rebalance frequency %(conn_rebalance)s')

    def has_ifc_delta_cfg(self):
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            if self.is_removable: #delete operation required
                self.delta_ifc_key = self.create_delta_ifc_key(cli)
                if cli.startswith(self.asa_key):
                    self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': self.parse_cli(cli)}
                    "add it to its container's delta_ifc_cfg_value"
                    ancestor = self.get_ifc_delta_cfg_ancestor()
                    if ancestor:
                        ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if isinstance(cli, str):
            if self.get_cli() == cli:
                self.set_action(State.NOCHANGE)
            else:
                self.set_action(State.MODIFY)

    def set_action(self, state):
        'Set the state for this object'
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                value['state'] = state

        self.delta_ifc_cfg_value['state'] = state

    def get_action(self):
        '''
        @return the State for this object
        '''
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                return value['state']

    def parse_cli(self, cli):
        if isinstance(cli, str):
            tokens = cli.split()
            # CLI format is: 'conn-rebalance frequency <num>'
            if len(tokens) > 2:
                return tokens[2]

    def is_my_cli(self, cli):
        '''Determine if a CLI matches self.asa_key
        @param cil: str or StructuredCommand
        @return boolean, True if self.asa_key matches CLI, or False
        '''

        if isinstance(cli, str):
            command = cli.strip()
        elif isinstance(cli, StructuredCommand):
            command = cli.command
        return command.startswith(self.asa_key)

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_ifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        if not self.has_ifc_delta_cfg():
            return ''

        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return ' '.join((self.asa_gen_template % value).split())


class ConsoleReplicate(DMBoolean):
    'Translator for cluster console-replicate sub-command'

    def __init__(self):
        DMBoolean.__init__(self, ifc_key = 'console_replicate',
                            asa_key = 'console-replicate',
                            on_value = 'enable')

    def has_ifc_delta_cfg(self):
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def set_action(self, state):
        'Set the state for this object'
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                value['state'] = state

        self.delta_ifc_cfg_value['state'] = state

    def get_action(self):
        '''
        @return the State for this object
        '''
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                return value['state']

    def is_my_cli(self, cli):
        '''Determine if a CLI matches self.asa_key
        @param cil: str or StructuredCommand
        @return boolean, True if self.asa_key matches CLI, or False
        '''

        if isinstance(cli, str):
            command = cli.strip()
        elif isinstance(cli, StructuredCommand):
            command = cli.command
        return command.startswith(self.asa_key)

    def parse_cli(self, cli):
        if isinstance(cli, str):
            tokens = cli.split()
            # CLI format is: 'cosole-replicate'
            if len(tokens) > 0:
                return tokens[0]

    def get_cli(self):
        return self.asa_key

    def diff_ifc_asa(self, cli):
        # When this function is called, it implies ASA already have 'console-replicate'
        # We could either delete it or NOCHANGE.
        # MODIFY is not possible as this CLI doesn't have any variable parameter.
        if not self.has_ifc_delta_cfg():
            if self.is_removable: #delete operation required
                self.delta_ifc_key = self.create_delta_ifc_key(cli)
                self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': self.parse_cli(cli)}

                "add it to its container's delta_ifc_cfg_value"
                ancestor = self.get_ifc_delta_cfg_ancestor()
                if ancestor:
                    ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if isinstance(cli, str):
            if self.get_cli() == cli:
                self.set_action(State.NOCHANGE)


class HealthCheck(SimpleType):
    'Translator for cluster health check sub-command'
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'health_check',
                            asa_key = 'health-check',
                            asa_mode_template = 'cluster group %(group_name)s',
                            asa_gen_template = 'health-check holdtime %(health_check)s')

    def has_ifc_delta_cfg(self):
        if not hasattr(self, 'delta_ifc_cfg_value'):
            return False
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def set_action(self, state):
        'Set the state for this object'
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                value['state'] = state

        self.delta_ifc_cfg_value['state'] = state

    def get_action(self):
        '''
        @return the State for this object
        '''
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                return value['state']

    def parse_cli(self, cli):
        if isinstance(cli, str):
            tokens = cli.split()
            # CLI format is: 'conn-rebalance frequency <num>'
            if len(tokens) > 2:
                return tokens[2]

    def is_my_cli(self, cli):
        '''Determine if a CLI matches self.asa_key
        @param cil: str or StructuredCommand
        @return boolean, True if self.asa_key matches CLI, or False
        '''
        if not self.asa_key:
            return False
        if isinstance(cli, str):
            command = cli.strip()
        return command.startswith(self.asa_key)

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_iifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        if not self.has_ifc_delta_cfg():
            return ''

        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        'Take care of mode command'
        if self.asa_mode_template:
            assert isinstance(value, dict)
            self.mode_command = self.asa_mode_template % value

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            if self.is_removable: #delete operation required
                self.delta_ifc_key = self.create_delta_ifc_key(cli)
                self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': self.parse_cli(cli)}

                "add it to its container's delta_ifc_cfg_value"
                ancestor = self.get_ifc_delta_cfg_ancestor()
                if ancestor:
                    ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if isinstance(cli, str):
            if self.get_cli() == cli:
                self.set_action(State.NOCHANGE)
            else:
                self.set_action(State.MODIFY)


class SecretKey(SimpleType):
    'Translator for cluster secret key to authenticate units in cluster'
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'key',
                            asa_key = 'key',
                            asa_mode_template = 'cluster group %(group_name)s',
                            asa_gen_template = 'key %(key)s')

    def has_ifc_delta_cfg(self):
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def set_action(self, state):
        'Set the state for this object'
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                value['state'] = state

        self.delta_ifc_cfg_value['state'] = state

    def get_action(self):
        '''
        @return the State for this object
        '''
        key = self.delta_ifc_key
        cfg = self.delta_ifc_cfg_value['value']
        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            if key == self.ifc_key:
                return value['state']

    def is_my_cli(self, cli):
        '''Determine if a CLI matches self.asa_key
        @param cil: str or StructuredCommand
        @return boolean, True if self.asa_key matches CLI, or False
        '''
        if not self.asa_key:
            return False
        if isinstance(cli, str):
            command = cli.strip()
        return command.startswith(self.asa_key)

    def parse_cli(self, cli):
        if isinstance(cli, str):
            tokens = cli.split()
            # CLI format is: 'key <xyz>'
            if len(tokens) > 1:
                return tokens[1]

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_iifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        if not self.has_ifc_delta_cfg():
            return ''

        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        'Take care of mode command'
        if self.asa_mode_template:
            assert isinstance(value, dict)
            self.mode_command = self.asa_mode_template % value

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            if self.is_removable: #delete operation required
                self.delta_ifc_key = self.create_delta_ifc_key(cli)
                self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': self.parse_cli(cli)}

                "add it to its container's delta_ifc_cfg_value"
                ancestor = self.get_ifc_delta_cfg_ancestor()
                if ancestor:
                    ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if isinstance(cli, str):
            if self.get_cli() == cli:
                self.set_action(State.NOCHANGE)
            else:
                self.set_action(State.MODIFY)


class LocalUnit(SimpleType):
    'Translator for cluster local-unit name'
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'local_unit',
                            asa_key = 'local-unit',
                            asa_mode_template = 'cluster group %(group_name)s',
                            asa_gen_template = 'local-unit %(local_unit)s')

    def has_ifc_delta_cfg(self):
        if not hasattr(self, 'delta_ifc_cfg_value'):
            return False
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_iifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        if not self.has_ifc_delta_cfg():
            return ''

        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        'Take care of mode command'
        if self.asa_mode_template:
            assert isinstance(value, dict)
            self.mode_command = self.asa_mode_template % value

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())


class Priority(SimpleType):
    'Translator for cluster priority level to a cluser unit for master election'
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'priority',
                            asa_key = 'priority',
                            asa_mode_template = 'cluster group %(group_name)s',
                            asa_gen_template = 'priority %(priority)s')

    def has_ifc_delta_cfg(self):
        if not hasattr(self, 'delta_ifc_cfg_value'):
            return False
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.ifc_key in [str(v[0]) for v in value.items()]

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_iifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        'Take care of mode command'
        if self.asa_mode_template:
            assert isinstance(value, dict)
            self.mode_command = self.asa_mode_template % value

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())


class Clacp(SimpleType):
    '''
    This class represents the CLACP system-mac configuration of the cluster.
    '''

    def __init__(self):
        SimpleType.__init__(self, ifc_key='clacp',
                            asa_key = 'clacp system-mac',
                            asa_gen_template='clacp system-mac %(system_mac)s')

    def get_cli(self):
        '''Generate the CLI for this CLACP system-mac configuration.
        '''
        if not self.has_ifc_delta_cfg():
            return ''
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        priority = config.get('priority')
        result = SimpleType.get_cli(self)
        if priority:
            result += ' system-priority ' + priority
        return ' '.join(result.split())

    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        if not self.has_ifc_delta_cfg():
            return ''
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.asa_gen_template % value

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional parameter
        '''
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of tokens must greater than 3, i.e. 'clacp system-mac [H.H.H | auto]'
        assert len(tokens) > 3

        option = tokens[3:]
        if len(option) > 0:
            result[(Type.PARAM, 'system-priority', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'system-priority', '']['value'] = option[0]
        return result


class ClusterInterface(SimpleType):
    '''
    This class represents the cluster control link interface configuration.
    '''

    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'cluster_interface',
                            asa_key = 'cluster-interface',
                            asa_gen_template='cluster-interface %(interface)s ip %(ip)s %(mask)s',
                            is_removable = False,
                            response_parser = cluster_response_parser)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        @see DMObject.ifc2asa for parameter details
        '''
        if not self.has_ifc_delta_cfg():
            return
        action = self.get_action()
        if action == State.NOCHANGE:
            return

        if action in (State.CREATE, State.MODIFY):
            self.generate_cli(asa_cfg_list, self.get_cli())
            # 'no shutdown' the cluster control link interface
            intf = util.normalize_interface_name(self.get_top().get_ClusterControLink_interface())
            if intf:
                clii = CLIInteraction(mode_command='interface ' + intf, command='no shutdown')
                asa_cfg_list.append(clii)

    def get_cli(self):
        '''Return the CLI for the self.delta_ifc_cfg_value, used by ifc2asa.
        @precondition: self.has_iifc_detal_cfg() is True
        @note: it always returns the +ve CLI, i.e. no "no" prefix in the return value.
        '''
        if not self.has_ifc_delta_cfg():
            return ''

        value = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        value['interface'] = util.normalize_interface_name(self.get_top().get_ClusterControLink_interface())

        '''The following join, split, and strip, and split are used to rid of extra space characters
        that may result from empty optional parameters.
        '''
        return ' '.join((self.asa_gen_template % value).split())


class EnableCluster(DMBoolean):
    'Translator for enable or disable cluster'
    def __init__(self):
        DMBoolean.__init__(self, ifc_key = 'enable',
                            asa_key = 'enable',
                            on_value = 'enable',
                            response_parser=cluster_response_parser)

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''Store the ifc configuration for this object. It is used to generate ASA configuration on
        '''

        cfg = delta_ifc_cfg_value.get('value')
        if not isinstance(cfg, dict): #terminal node
            return

        for delta_ifc_key, value in cfg.iteritems():
            kind, key, instance = delta_ifc_key
            child = self.get_child(key)
            if key == self.ifc_key:
                self.delta_ifc_key = delta_ifc_key
                self.delta_ifc_cfg_value = value
                return

    def is_my_cli(self, cli):
        '''Determine if a CLI matches self.asa_key
        @param cil: str or StructuredCommand
        @return boolean, True if self.asa_key matches CLI, or False
        '''
        if not self.asa_key:
            return False
        if isinstance(cli, str):
            command = cli.strip()
        elif isinstance(cli, StructuredCommand):
            command = cli.command
        return command == self.asa_key

    def get_cli(self):
        if not self.has_ifc_delta_cfg():
            return
        prefix = 'no ' if self.delta_ifc_cfg_value['value'] != 'enable' else ''
        if self.delta_ifc_cfg_value['state'] == State.DESTROY:
            # append nothing if we're generating 'no enable' CLI
            suffix = ''
        else:
            suffix = ' noconfirm' if ClusterConfig.is_cluster_master() else ' as-slave'
        return prefix + self.asa_key + suffix

class ClusterMtu(SimpleType):
    '''
    This class represents the MTU of the cluster control link interface.
    '''

    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'mtu',
                            asa_key = 'mtu cluster',
                            asa_gen_template='mtu cluster %(mtu)s',
                            response_parser = cluster_response_parser)

    def get_cli(self):
        cfg = {self.delta_ifc_key: self.delta_ifc_cfg_value} \
              if isinstance(self.delta_ifc_cfg_value['value'], str) else self.delta_ifc_cfg_value['value']
        value = normalize_param_dict(cfg)
        return ' '.join((self.asa_gen_template % value).split())

def cluster_response_parser(response):
    '''
    Ignores INFO, WARNING, and some expected errors in the response, otherwise returns original.
    '''

    if response:
        msgs_to_ignore = ('INFO:',
                          'WARNING:',
                          'Interface does not have virtual MAC',
                          'No change to the stateful interface',
                          'Waiting for the earlier webvpn instance to terminate',
                          'Previous instance shut down',
                          'This unit is in syncing state',
                          'Configuration syncing is in progress',
                          'The requested mode is the SAME as the current mode',
                          'Detected Cluster Master')
        found_msg_to_ignore = False
        for msg in msgs_to_ignore:
            if msg in response:
                found_msg_to_ignore = True
    return None if response and found_msg_to_ignore else response
