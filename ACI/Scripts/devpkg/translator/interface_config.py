'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''

from base.dmobject import DMObject
from translator.base.dmlist import DMList
from base.simpletype import SimpleType
from translator.state_type import State, Type
import asaio.cli_interaction as cli_interaction
import utils.util as util
import re

class InterfaceConfig(DMObject):
    def __init__(self, instance):
        DMObject.__init__(self, instance)
        self.register_child(IPv4Addr('ipv4_address'))
        self.register_child(SecurityLevel('security_level'))
        self.register_child(IPv6AddrList())
        self.register_child(IPv6AutoConfig('ipv6_autoconfig'))
        self.register_child(IPv6Enable('ipv6_enable'))
        self.register_child(IPv6NDDad('ipv6_nd_dad_attempts'))
        self.register_child(IPv6NDNsInterval('ipv6_nd_ns_interval'))
        self.register_child(IPv6NDReachable('ipv6_nd_reachable_time'))
        self.register_child(IPv6NDRaInterval('ipv6_nd_ra_interval'))
        self.register_child(IPv6NDRaLifetime('ipv6_nd_ra_lifetime'))
        self.register_child(IPv6LinkLocal('ipv6_link_local_address'))
        self.register_child(IPv6NeighborDiscoveryList())
        'vxlan config below'
        self.register_child(SegmentIDSecondarys())
        self.register_child(SegmentIDOriginates())

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        DMObject.populate_model(self, delta_ifc_key, delta_ifc_cfg_value)
        self.state = delta_ifc_cfg_value['state']

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        pass

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, mode):
        if not self.has_ifc_delta_cfg():
            return

        if self.state == State.NOCHANGE:
            return

        for child in self.children.values():
            child.mode_command = mode
            child.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list)

    def gen_diff_ifc_asa(self, cli_dict):
        '''
        Check if any state changes needed
        '''
        my_state = []
        for child in self.children.values():
            my_state.append(child.gen_diff_ifc_asa(cli_dict))

        if State.MODIFY in my_state or State.DESTROY in my_state:
            return State.MODIFY
        elif State.NOCHANGE in my_state:
            return State.NOCHANGE

class InterfaceSimpleType(SimpleType):
    'base class for interface sub-command'
    def __init__(self, ifc_key, asa_gen_template):
        SimpleType.__init__(self, ifc_key = ifc_key, asa_gen_template = asa_gen_template)
        self.cli_key = ''
        self.response_parser = cli_interaction.ignore_info_response_parser

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''Generate ASA configuration from IFC configuration delta.
        @see SimpleType.ifc2asa for parameter details
        '''
        SimpleType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def gen_diff_ifc_asa(self, cli_dict):
        if not self.cli_key in cli_dict:
            return
        SimpleType.diff_ifc_asa(self, cli_dict[self.cli_key])
        return self.get_action()

class SecurityLevel(InterfaceSimpleType):
    'Model after "security-level <0-100>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='security-level %s')
        self.cli_key = 'security-level'

class IPv4Addr(InterfaceSimpleType):
    'Model after "ip address ipv4_address netmask" sub-command'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ip address %s')
        self.cli_key = 'ip'

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        value = self.get_value()
        if '.' in value: #ipv4 address
            value = ' '.join(value.split('/'))
        return self.asa_gen_template % value

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because the IPv4 address is entered as an address and netmask tuple'
        return '/'.join(cli.split()[1:])

class IPv6AutoConfig(InterfaceSimpleType):
    'Model after "ipv6 address autoconfig'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 address autoconfig')
        self.cli_key = 'autoconfig'

    def parse_cli(self, cli):
        '''Override
        '''
        return cli

    def get_cli(self):
        '''Generate the CLI for this single logging host config.
        '''
        return self.asa_gen_template

class IPv6Enable(InterfaceSimpleType):
    'Model after "ipv6 enable'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 enable')
        self.cli_key = 'enable'

    def parse_cli(self, cli):
        '''Override
        '''
        return cli

    def get_cli(self):
        '''Generate the CLI for this single logging host config.
        '''
        return self.asa_gen_template

class IPv6NDDad(InterfaceSimpleType):
    'Model after  "ipv6 nd dad attempts <0-600>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 nd dad attempts %s')
        self.cli_key = 'dad'

class IPv6NDNsInterval(InterfaceSimpleType):
    'Model after  "ipv6 nd ns-interval <1000-3600000 ms>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 nd ns-interval %s')
        self.cli_key = 'ns-interval'

class IPv6NDReachable(InterfaceSimpleType):
    'Model after  "ipv6 nd reachable-time <0-3600000 ms>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 nd reachable-time %s')
        self.cli_key = 'reachable-time'

class IPv6NDRaInterval(InterfaceSimpleType):
    'Model after  "ipv6 nd ra-interval <500-1800000 ms>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 nd ra-interval %s')
        self.cli_key = 'ra-interval'

class IPv6NDRaLifetime(InterfaceSimpleType):
    'Model after  "ipv6 nd ra-lifetime <0-9000 seconds>'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 nd ra-lifetime %s')
        self.cli_key = 'ra-lifetime'

class IPv6LinkLocal(InterfaceSimpleType):
    'Model after  "ipv6 address x:x:x:x::x link-local'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 address %s link-local')
        self.cli_key = 'link-local'

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        config = util.normalize_ipv6_address(config)
        return self.asa_gen_template % config

class IPv6AddrList(DMList):
    'Container of IPV6Addr'
    def __init__(self):
        DMList.__init__(self, name='IPv6Address', asa_key='ipv6 address', child_class=IPv6Addr)

    def gen_ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        for child in self.children.values():
            child.mode_command = self.mode_command
            child.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list)

    def gen_diff_ifc_asa(self, ipv6_cli_dict):
        my_state = []
        if not ipv6_cli_dict:
            return

        for cli in ipv6_cli_dict.values():
            result = DMList.get_translator(self, cli)
            if result:
                my_state.append(result.gen_diff_ifc_asa(cli))

        if State.MODIFY in my_state:
            return State.MODIFY
        if State.DESTROY in my_state:
            return State.DESTROY
        if State.NOCHANGE in my_state:
            return State.NOCHANGE

    def is_my_cli(self, cli):
        tokens = cli.split(' ')
        return cli.startswith('ipv6 address') and '/' in tokens[2]

class IPv6Addr(InterfaceSimpleType):
    'Model after "ipv6 address ipv6_address/prefix [eui-64]" sub-command'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance, 
                            asa_gen_template='ipv6 address %(ipv6_address_with_prefix)s')

    def create_asa_key(self):
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        value['ipv6_address_with_prefix'] = util.normalize_ipv6_address(value['ipv6_address_with_prefix'])
        return self.asa_gen_template % value

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        config['ipv6_address_with_prefix'] = util.normalize_ipv6_address(config['ipv6_address_with_prefix'])              
        eui64 = config.get('eui64')
        eui64 = ' eui-64' if eui64 else ''
        result = 'ipv6 address ' + config['ipv6_address_with_prefix']
        result += eui64
        return ' '.join(result.split())

    def parse_multi_parameter_cli(self, cli):
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of tokens must greater than 2, i.e. 'ipv6 address x:x:x:x::x/prefix eui-64'
        assert len(tokens) > 2

        if len(tokens) == 4:
            result[(Type.PARAM, 'eui64', '')] = {'state': State.NOCHANGE, 'value': ''}
            result[Type.PARAM, 'eui64', '']['value'] = 'enable'
        return result

    def gen_diff_ifc_asa(self, cli):
        if not 'ipv6' in cli:
            return
        SimpleType.diff_ifc_asa(self, cli)
        return self.get_action()

class IPv6NeighborDiscoveryList(DMList):
    'Container of IPV6Addr'
    def __init__(self):
        DMList.__init__(self, name='IPv6NeighborDiscovery', asa_key='ipv6 nd prefix', child_class=IPv6NeighborDiscovery)

    def gen_ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        for child in self.children.values():
            child.mode_command = self.mode_command
            child.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list)

    def gen_diff_ifc_asa(self, ipv6_cli_dict):
        my_state = []
        if not ipv6_cli_dict:
            return

        for cli in ipv6_cli_dict.values():
            result = DMList.get_translator(self, cli)
            if result:
                my_state.append(result.gen_diff_ifc_asa(cli))

        if State.MODIFY in my_state:
            return State.MODIFY
        if State.DESTROY in my_state:
            return State.DESTROY
        if State.NOCHANGE in my_state:
            return State.NOCHANGE

    def is_my_cli(self, cli):
        return cli.startswith('ipv6 nd prefix')

class IPv6NeighborDiscovery(InterfaceSimpleType):
    'Model after "ipv6 nd prefix x:x:x:x::/prefix|default [s1 s2] [at d1 d2] [no-advertise] [no-autoconfig] [off-link]" sub-command'
    def __init__(self, instance):
        InterfaceSimpleType.__init__(self, ifc_key = instance,
                            asa_gen_template='ipv6 nd prefix %(prefix_or_default)s')

    def create_asa_key(self):
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if value['prefix_or_default']  != 'default':
            value['prefix_or_default'] = util.normalize_ipv6_address(value['prefix_or_default'])
        d1 = value.get('valid_lifetime_in_seconds')
        d2 = value.get('prefered_lifetime_in_seconds')
        if d1 and d2:
            t1 = d1.split()
            t2 = d2.split()
            if len(t1) > 3:
                d1 = ' '.join(t1[0:3])
            if len(t2) > 3:
                d2 = ' '.join(t2[0:3])
            value['valid_lifetime_in_seconds'] = d1
            value['prefered_lifetime_in_seconds'] = d2
        return self.asa_gen_template % value

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if config['prefix_or_default']  != 'default':
            config['prefix_or_default'] = util.normalize_ipv6_address(config['prefix_or_default'])
        valid_lifetime_in_seconds = config.get('valid_lifetime_in_seconds')
        valid_lifetime_never_expire = config.get('valid_lifetime_never_expire')
        prefered_lifetime_in_seconds = config.get('prefered_lifetime_in_seconds')
        prefered_lifetime_never_expire = config.get('prefered_lifetime_never_expire')
        valid_lifetime_in_date = config.get('valid_lifetime_in_date')
        prefered_lifetime_in_date = config.get('prefered_lifetime_in_date')
        s1 = valid_lifetime_in_seconds if valid_lifetime_in_seconds else valid_lifetime_never_expire
        s2 = prefered_lifetime_in_seconds if prefered_lifetime_in_seconds else prefered_lifetime_never_expire
        d1 = valid_lifetime_in_date if valid_lifetime_in_date else ''
        d2 = prefered_lifetime_in_date if prefered_lifetime_in_date else ''
        result = 'ipv6 nd prefix ' + config['prefix_or_default']
        if s1 and s2:
            result += ' ' + s1 + ' ' + s2
        elif d1 and d2:
            d1 = self.get_date_without_year(d1)
            d2 = self.get_date_without_year(d2)
            result += ' at ' + d1 + ' ' + d2

        no_advertise = config.get('no_advertise')
        no_autoconfig = config.get('no_autoconfig')
        off_link = config.get('off_link')

        if no_advertise:
            result += ' no-advertise'
        else:
            if off_link:
                result += ' off-link'
            if no_autoconfig:
                result += ' no-autoconfig'
        return ' '.join(result.split())

    def get_date_without_year(self, date_cli):
        p1 = re.compile('^(\S+) (\d+) (\d+) (\S+)')
        p2 = re.compile('^(\d+) (\S+) (\d+) (\S+)')

        m1 = p1.match(date_cli)
        m2 = p2.match(date_cli)
        m = m1 if m1 else m2
        if m:
            return ' '.join(m.group(1, 2, 4))
        else:
            return date_cli

    def parse_multi_parameter_cli(self, cli):
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of tokens must greater than 2, i.e. 'ipv6 address prefix or default'
        assert len(tokens) > 2

        if ' at ' in cli:
            colon_index_list = [a for a,b in enumerate(tokens) if ':' in b]
            d1 = self.get_date_without_year(' '.join(tokens[5:colon_index_list[0]+1]))
            d2 = self.get_date_without_year(' '.join(tokens[(colon_index_list[0] + 1):colon_index_list[1]+1]))

            result[(Type.PARAM, 'valid_lifetime_in_date', '')] = {'state': State.NOCHANGE, 'value': d1}
            result[(Type.PARAM, 'prefered_lifetime_in_date', '')] = {'state': State.NOCHANGE, 'value': d2}
        elif len(tokens) > 5 and (tokens[4].isdigit() or tokens[4] == 'infinite') and \
            (tokens[5].isdigit() or tokens[5] == 'infinite'):
            s1 = 'valid_lifetime_in_seconds' if tokens[5].isdigit() else 'valid_lifetime_never_expire'
            s2 = 'prefered_lifetime_in_seconds' if tokens[5].isdigit() else 'prefered_lifetime_never_expire'
            result[(Type.PARAM, s1, '')] = {'state': State.NOCHANGE, 'value': tokens[4]}
            result[(Type.PARAM, s2, '')] = {'state': State.NOCHANGE, 'value': tokens[5]}
        if 'no-advertise' in cli:
            result[(Type.PARAM, 'no_advertise', '')] = {'state': State.NOCHANGE, 'value': 'enable'}
        else:
            if 'off-link' in cli:
                result[(Type.PARAM, 'off-link', '')] = {'state': State.NOCHANGE, 'value': 'enable'}
            if 'no-autoconfig' in cli:
                result[(Type.PARAM, 'no-autoconfig', '')] = {'state': State.NOCHANGE, 'value': 'enable'}
        return result

    def gen_diff_ifc_asa(self, cli):
        if not 'ipv6 nd prefix' in cli:
            return
        SimpleType.diff_ifc_asa(self, cli)
        return self.get_action()

class SegmentIDList(DMList):
    'Segment ID list for secondary and originate'
    def __init__(self, name, child_class):
        DMList.__init__(self, name, child_class, asa_key='segment-id')
        self.segment_key = ''

    def gen_ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        for child in self.children.values():
            child.mode_command = self.mode_command
            child.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list)

    def gen_diff_ifc_asa(self, cli_dict):
        my_state = []
        if not cli_dict:
            return
        for cli in cli_dict.values():
            result = DMList.get_translator(self, cli)
            if result:
                my_state.append(result.gen_diff_ifc_asa(cli))
        if State.MODIFY in my_state:
            return State.MODIFY
        if State.DESTROY in my_state:
            return State.DESTROY
        if State.NOCHANGE in my_state:
            return State.NOCHANGE

    def is_my_cli(self, cli):
        return cli.startswith('segment-id') and self.segment_key in cli

class SegmentIDSecondarys(SegmentIDList):
    'Secondary segment ID list'
    def __init__(self):
        SegmentIDList.__init__(self, name='segment_id_secondary', child_class=SegmentIDSecondary)
        self.segment_key = 'secondary'

class SegmentIDOriginates(SegmentIDList):
    'Originate segment ID list'
    def __init__(self):
        SegmentIDList.__init__(self, name='segment_id_originate', child_class=SegmentIDOriginate)
        self.segment_key = 'originate'

class SegmentIDSimpleType(InterfaceSimpleType):
    'Model after "segment-id <1-16million> [secondary|originate]'
    def __init__(self, instance, asa_gen_template, key):
        InterfaceSimpleType.__init__(self, ifc_key = instance, asa_gen_template=asa_gen_template)
        self.segment_key = key

    def is_my_cli(self, cli):
        tokens = cli.split(' ')
        num = self.delta_ifc_cfg_value['value']
        return tokens[1] == num

    def gen_diff_ifc_asa(self, cli):
        if cli.startswith('segment-id') and self.segment_key in cli:
            SimpleType.diff_ifc_asa(self, cli)
            return self.get_action()

class SegmentIDSecondary(SegmentIDSimpleType):
    'Model after "segment-id <1-16million> secondary'
    def __init__(self, instance):
        SegmentIDSimpleType.__init__(self, instance,'segment-id %s secondary', 'secondary')

class SegmentIDOriginate(SegmentIDSimpleType):
    'Model after "segment-id <1-16million> originate'
    def __init__(self, instance):
        SegmentIDSimpleType.__init__(self, instance,'segment-id %s originate', 'originate')
