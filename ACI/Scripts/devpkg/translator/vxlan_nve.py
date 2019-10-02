'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''

import translator
from base.dmobject import DMObject
from base.simpletype import SimpleType
from base.compositetype import CompositeType
from translator.state_type import State, Type
from translator.base.dmlist import DMList
import asaio.cli_interaction as cli_interaction
from translator.structured_cli import StructuredCommand
import utils.util as util
from translator.bridge_group_interface import IPv4Addr, IPv6Addr, IPv6Enable, IPv6NDDad, IPv6NDNsInterval,IPv6NDReachable


class VxlanPort(SimpleType):
    'Model after  "vxlan port <port_num>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'vxlan port', \
                            asa_gen_template='vxlan port %s')
class NVE(CompositeType):
    def __init__(self, name):
        SimpleType.__init__(self, name);
        self.register_child(Peer('Peer'))
        self.register_child(SourceInterface('source_interface'))
        self.response_parser = cli_interaction.ignore_info_response_parser
        self.encapsulation = Encapsulation()

    def is_my_cli(self, cli):
        if not isinstance(cli, StructuredCommand):
            return False
        return 'nve 1' in cli.command

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if not self.has_ifc_delta_cfg() or not self.delta_ifc_cfg_value['value']:
            return
        state = self.get_action()
        if state == State.NOCHANGE:
            return
        if self.get_action() == State.DESTROY:
            'To generate the no form of the command'

            self.generate_cli(asa_cfg_list, 'no nve 1')
            return
        'Generate CLIs from the children'
        child_mode_command = self.get_cli()
        for child in self.children.values():
            child.mode_command = child_mode_command
            child.ifc2asa(no_asa_cfg_stack, asa_cfg_list)
        if state in [State.CREATE, State.MODIFY]:
            self.encapsulation.mode_command = child_mode_command
            self.encapsulation.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, state)

    def get_cli(self):
        return 'nve 1'

    def diff_ifc_asa(self, cli):
        ''' Need to override this method because in composite type, the config value
            is initialized with empty value.  The function has_ifc_delta_cfg() will
            not return false since the delta_ifc_cfg_value is not NONE.
        '''
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if not self.has_ifc_delta_cfg() or not config:
            if self.is_removable: #delete operation required
                self.delta_ifc_key = self.create_delta_ifc_key(cli)
                self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': self.parse_cli(cli)}

                "add it to its container's delta_ifc_cfg_value"
                ancestor = self.get_ifc_delta_cfg_ancestor()
                if ancestor:
                    ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if isinstance(cli, str):
            assert cli.strip().startswith(self.get_asa_key())
        elif isinstance(cli, StructuredCommand):
            assert cli.command.startswith(self.get_asa_key())
        'Use dictionary compare instead of CLI compare to take care of optional parameters'
        if self.is_the_same_cli(cli):
            self.set_action(State.NOCHANGE)
        else:
            self.set_action(State.MODIFY)
        if self.get_action() == State.DESTROY:
            return

        for cmd in cli.sub_commands:
            translator = self.get_child_translator(cmd)
            if translator:
                translator.diff_ifc_asa(cmd)

class Peer(SimpleType):
    'Model after "peer ip <IP> [mac <MAC>]" sub-command'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_gen_template='peer ip %(peer_ip)s')

    def create_asa_key(self):
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.asa_gen_template % config
        return self.get_cli()

    def get_cli(self):
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        peer_mac = config.get('peer_mac')
        peer_mac = ' mac ' + peer_mac if peer_mac else ''
        return self.asa_gen_template % config + peer_mac

    def parse_multi_parameter_cli(self, cli):
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)
        tokens = cli.split()
        if len(tokens) == 3:
            return result # no optional parameter
        result[(Type.PARAM, 'peer_mac', '')] = {'state': State.NOCHANGE, 'value': ''}
        option = tokens[3:]
        if 'mac' in option: # e.g. "peer ip 10.10.10.10 mac 1234.5678.9abc"
            result[Type.PARAM, 'peer_mac', '']['value'] = option[1]
        return result

class Encapsulation(DMObject):
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        pass

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        pass

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, state):
        self.generate_cli(asa_cfg_list, 'encapsulation vxlan')

class SourceInterface(SimpleType):
    'Model after "source-interface <nameif>" sub-command'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_gen_template='source-interface %s')

    def create_asa_key(self):
        return self.get_cli()

    def get_cli(self):
        return self.asa_gen_template % self.get_value()

class TVIs(DMList):
    'Container of TVI'
    def __init__(self):
        DMList.__init__(self, name='TVI', asa_key='interface TVI1', child_class=TVI)

    def is_my_cli(self, cli):
        if not isinstance(cli, StructuredCommand):
            return False

        for child in self.children.values():
            if cli.command == child.get_cli():
                return True
        return False  # ignore interface TVI that are not in our list.  Phase1 only has 1 tvi

class TVI(CompositeType):
    'Model for "interface TVI" CLI'
    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='interface TVI1');  # Phase 1 only has TVI1
        self.register_child(IPv4Addr('ipv4_address'))
        self.register_child(DMList(name='ipv6_address_with_prefix', child_class=IPv6Addr, asa_key ='ipv6 address'))
        self.register_child(IPv6Enable('ipv6_enable'))
        self.register_child(IPv6NDDad('ipv6_nd_dad_attempts'))
        self.register_child(IPv6NDNsInterval('ipv6_nd_ns_interval'))
        self.register_child(IPv6NDReachable('ipv6_nd_reachable_time'))
        self.register_child(MACAddr('mac-address'))
        self.register_child(NameIF('nameif'))
        self.response_parser = cli_interaction.ignore_info_response_parser

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if self.has_ifc_delta_cfg():
            CompositeType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def is_my_cli(self, cli):
        if not isinstance(cli, StructuredCommand):
            return False
        return 'TVI1' in cli.command

class MACAddr(SimpleType):
    'Model after  "mac-address <H.H.H>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'mac-address', \
                            asa_gen_template='mac-address %s')

class NameIF(SimpleType):
    'Model after  "nameif <name>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'nameif', \
                            asa_gen_template='nameif %s')
