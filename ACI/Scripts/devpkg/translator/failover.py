'''
Created on Aug 23, 2013

@author: feliu
'''

from translator.base.dmobject import DMObject
from translator.base.dmlist import DMList
from translator.base.simpletype import SimpleType
from translator.base.dmboolean import DMBoolean
import utils.util as util
from asaio.cli_interaction import CLIInteraction
from translator.state_type import Type, State
import re

class FailoverConfig(DMObject):
    '''
    This class represents the holder of all failover configuration.
    '''

    def __init__(self):
        DMObject.__init__(self, FailoverConfig.__name__)
        ifc_asa_keys = (
                        ("lan_unit",          "failover lan unit"),
                        ("key_secret",        "failover key"),
                        ("key_in_hex",        "failover key hex"),
                        ("interface_policy",  "failover interface-policy")
                        )
        for ifc, asa in ifc_asa_keys:
            self.register_child(SimpleType(ifc, asa, response_parser=failover_response_parser))
        self.register_child(DMBoolean('http_replication', 'failover replication http', on_value="enable",
                            response_parser=failover_response_parser))
        self.register_child(DMList('mgmt_standby_ip', MgmtStandbyIP, asa_key='ip address'))
        self.register_child(DMList('failover_lan_interface', FailoverLANInterface, asa_key='failover lan interface'))
        self.register_child(DMList('failover_link_interface', FailoverLinkInterface, asa_key='failover link'))
        self.register_child(DMList('failover_ip', FailoverIP, asa_key='failover interface ip'))
        self.register_child(DMList('polltime', FailoverPolltime, asa_key='failover polltime'))
        self.response_parser = failover_response_parser
        self.register_child(DMBoolean(ifc_key = "failover", asa_key = "failover", on_value="enable",
                            response_parser=failover_response_parser))

class MgmtStandbyIP(SimpleType):
    '''
    This class represents the holder of management interface configuration of the standby IP.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name, is_removable = True,
                            asa_gen_template = "ip address %(active_ip)s %(netmask)s standby %(standby_ip)s",
                            asa_mode_template = "interface %(interface)s",
                            response_parser = failover_response_parser)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        '''

        if not self.has_ifc_delta_cfg():
            return
        action = self.delta_ifc_cfg_value['state']
        if action == State.NOCHANGE:
            return

        intf = util.normalize_param_dict(self.get_top().get_mgmt_interface())
        if not intf:
            return
        if self.is_cli_mode:
            if action in (State.CREATE, State.MODIFY):
                asa_cfg_list.append(self.get_cli())
            elif action == State.DESTROY and self.is_removable:
                self.generate_cli(asa_cfg_list, 'no ' + self.get_cli())

    def get_cli(self):
        '''
        Normalize the interface name before filling the template.
        '''
        assert self.has_ifc_delta_cfg()
        intf = util.normalize_param_dict(self.get_top().get_mgmt_interface())
        if not intf:
            return

        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        command = ' '.join((self.asa_gen_template % value).split())
        mode_command = 'interface ' + intf
        return CLIInteraction(command=command, mode_command=mode_command,
                              response_parser = failover_response_parser)

class FailoverLANInterface(SimpleType):
    '''
    This class represents the holder of failover LAN-based interface configuration.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='failover lan interface %(interface_name)s %(interface)s',
                            response_parser = failover_response_parser)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        '''

        if not self.has_ifc_delta_cfg():
            return
        action = self.delta_ifc_cfg_value['state']
        if action == State.NOCHANGE:
            return

        if self.is_cli_mode:
            if action in (State.CREATE, State.MODIFY):
                self.generate_cli(asa_cfg_list, self.get_cli())
                intf = util.normalize_param_dict(self.get_top().get_failover_lan_interface())
                if intf:
                    mode_cmd = 'interface ' + intf
                    asa_cfg_list.append(CLIInteraction(command='no shutdown', mode_command=mode_cmd,
                                                       response_parser = failover_response_parser))
            elif action == State.DESTROY and self.is_removable:
                self.generate_cli(asa_cfg_list, 'no ' + self.get_cli())

    def get_cli(self):
        '''
        Normalize the interface name before filling the template.
        '''
        assert self.has_ifc_delta_cfg()

        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        value['interface'] = util.normalize_interface_name(self.get_top().get_failover_lan_interface())

        return ' '.join((self.asa_gen_template % value).split())

class FailoverLinkInterface(SimpleType):
    '''
    This class represents the holder of failover link (stateful) interface configuration.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='failover link %(interface_name)s %(interface)s',
                            response_parser = failover_response_parser)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        '''

        if not self.has_ifc_delta_cfg():
            return
        action = self.delta_ifc_cfg_value['state']
        if action == State.NOCHANGE:
            return

        if self.is_cli_mode:
            if action in (State.CREATE, State.MODIFY):
                self.generate_cli(asa_cfg_list, self.get_cli())
                intf = util.normalize_param_dict(self.get_top().get_failover_link_interface())
                if intf:
                    mode_cmd = 'interface ' + intf
                    asa_cfg_list.append(CLIInteraction(command='no shutdown', mode_command=mode_cmd))
            elif action == State.DESTROY and self.is_removable:
                self.generate_cli(asa_cfg_list, 'no ' + self.get_cli())

    def get_cli(self):
        '''
        Normalize the interface name before filling the template.
        '''
        assert self.has_ifc_delta_cfg()

        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        value['interface'] = util.normalize_interface_name(self.get_top().get_failover_link_interface())

        return ' '.join((self.asa_gen_template % value).split())

class FailoverIP(SimpleType):
    '''
    This class represents the holder of failover IP configuration.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name, is_removable=True,
                            asa_gen_template='failover interface ip %(interface_name)s %(active_ip)s',
                            response_parser = failover_response_parser)

    def get_cli(self):
        '''Generate the CLI for this single failover ip config.
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        netmask = config.get('netmask') if ':' not in config.get('active_ip') else ''
        standby_ip = config.get('standby_ip')
        result = SimpleType.get_cli(self)
        result += ' ' + netmask + ' standby ' + standby_ip
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
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of tokens must greater than 3, i.e. 'failover interface ip ...'
        assert len(tokens) > 3

        for name  in ['interface_name', 'active_ip', 'standby_ip']:
            result[(Type.PARAM, name, '')] = {'state': State.NOCHANGE, 'value': ''}
        option = tokens[3:]
        # for ipv4, option is: %(interface_name)s %(active_ip)s %(netmask)s standby %(standby_ip)s
        # for ipv6, option is: %(interface_name)s %(active_ip)s standby %(standby_ip)s
        result[Type.PARAM, 'interface_name', '']['value'] = option[0]
        result[Type.PARAM, 'active_ip', '']['value'] = option[1]
        if ':' not in option[1]: # ipv4
            result[(Type.PARAM, 'netmask', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'netmask', '']['value'] = option[2]
            # skip option[3], which should be the 'standby' keyword
            result[Type.PARAM, 'standby_ip', '']['value'] = option[4]
        else: # ipv6, no netmask
            # skip option[2], which should be the 'standby' keyword
            result[Type.PARAM, 'standby_ip', '']['value'] = option[3]
        return result

class FailoverPolltime(SimpleType):
    '''
    This class represents the holder of failover polltime configuration.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='failover polltime',
                            response_parser = failover_response_parser)

    def get_cli(self):
        '''Generate the CLI for the failover polltime config.
        '''

        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        unit_or_interface = config.get('unit_or_interface')
        unit_or_interface = ' ' + unit_or_interface if unit_or_interface else ''
        interval_in_second = config.get('interval_in_second')
        interval_in_second = ' ' + interval_in_second if interval_in_second else ''
        interval_in_msec = config.get('interval_in_msec')
        interval_in_msec = ' msec ' + interval_in_msec if interval_in_msec else ''
        holdtime_in_second = config.get('holdtime_in_second')
        holdtime_in_second = ' holdtime ' + holdtime_in_second if holdtime_in_second else ''
        holdtime_in_msec = config.get('holdtime_in_msec')
        holdtime_in_msec = ' holdtime msec ' + holdtime_in_msec if holdtime_in_msec else ''
        return 'failover polltime' + unit_or_interface + interval_in_second + \
                interval_in_msec + holdtime_in_second + holdtime_in_msec

    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.asa_gen_template % value

    def parse_cli(self, cli):
        '''
        Discover the value for this object from given CLI
        '''
        # Valid examples:
        # 1.  failover polltime 5
        # 2.  failover polltime 5 holdtime 15
        # 3.  failover polltime msec 200
        # 4.  failover polltime msec 200 holdtime 1
        # 5.  failover polltime msec 200 holdtime msec 800
        # 6.  failover polltime interface|unit 5
        # 7.  failover polltime interface|unit 5 holdtime 15
        # 8.  failover polltime interface|unit msec 200
        # 9.  failover polltime interface|unit msec 200 holdtime 1
        # 10. failover polltime interface|unit msec 200 holdtime msec 800

        p1 = re.compile('^failover polltime \d+$')
        p2 = re.compile('^failover polltime \d+ holdtime \d+$')
        p3 = re.compile('^failover polltime msec \d+$')
        p4 = re.compile('^failover polltime msec \d+ holdtime \d+$')
        p5 = re.compile('^failover polltime msec \d+ holdtime msec \d+$')
        p6 = re.compile('^failover polltime (interface|unit) \d+$')
        p7 = re.compile('^failover polltime (interface|unit) \d+ holdtime \d+$')
        p8 = re.compile('^failover polltime (interface|unit) msec \d+$')
        p9 = re.compile('^failover polltime (interface|unit) msec \d+ holdtime \d+$')
        p10= re.compile('^failover polltime (interface|unit) msec \d+ holdtime msec \d+$')

        index_unit_or_interface = None
        index_interval_in_second = None
        index_interval_in_msec = None
        index_holdtime_in_second = None
        index_holdtime_in_msec = None

        if p1.match(cli):   # failover polltime 5
            index_interval_in_second = 2
        elif p2.match(cli): # failover polltime 5 holdtime 15
            index_interval_in_second = 2
            index_holdtime_in_second = 4
        elif p3.match(cli): # failover polltime msec 200
            index_interval_in_msec = 3
        elif p4.match(cli): # failover polltime msec 200 holdtime 1
            index_interval_in_msec = 3
            index_holdtime_in_second = 5
        elif p5.match(cli): # failover polltime msec 200 holdtime msec 800
            index_interval_in_msec = 3
            index_holdtime_in_msec = 6
        elif p6.match(cli): # failover polltime interface|unit 5
            index_unit_or_interface = 2
            index_interval_in_second = 3
        elif p7.match(cli): # failover polltime interface|unit 5 holdtime 15
            index_unit_or_interface = 2
            index_interval_in_second = 3
            index_holdtime_in_second = 5
        elif p8.match(cli): # failover polltime interface|unit msec 200
            index_unit_or_interface = 2
            index_interval_in_msec = 4
        elif p9.match(cli): # failover polltime interface|unit msec 200 holdtime 1
            index_unit_or_interface = 2
            index_interval_in_msec = 4
            index_holdtime_in_second = 6
        elif p10.match(cli):# failover polltime interface|unit msec 200 holdtime msec 800
            index_unit_or_interface = 2
            index_interval_in_msec = 4
            index_holdtime_in_msec = 7

        tokens = cli.split()
        result = {}
        if index_unit_or_interface:
            result[(Type.PARAM, 'unit_or_interface', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'unit_or_interface', '']['value'] = tokens[index_unit_or_interface]
        if index_interval_in_second:
            result[(Type.PARAM, 'interval_in_second', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'interval_in_second', '']['value'] = tokens[index_interval_in_second]
        if index_interval_in_msec:
            result[(Type.PARAM, 'interval_in_msec', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'interval_in_msec', '']['value'] = tokens[index_interval_in_msec]
        if index_holdtime_in_second:
            result[(Type.PARAM, 'holdtime_in_second', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'holdtime_in_second', '']['value'] = tokens[index_holdtime_in_second]
        if index_holdtime_in_msec:
            result[(Type.PARAM, 'holdtime_in_msec', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'holdtime_in_msec', '']['value'] = tokens[index_holdtime_in_msec]
        return result

def failover_response_parser(response):
    '''
    Ignores INFO, WARNING, and some expected errors in the response, otherwise returns original.
    '''

    if response:
        msgs_to_ignore = ('INFO:',
                          'WARNING',
                          'Interface does not have virtual MAC',
                          'No change to the stateful interface',
                          'Waiting for the earlier webvpn instance to terminate',
                          'This unit is in syncing state',
                          'Configuration syncing is in progress')
        found_msg_to_ignore = False
        for msg in msgs_to_ignore:
            if msg in response:
                found_msg_to_ignore = True
    return None if response and found_msg_to_ignore else response
