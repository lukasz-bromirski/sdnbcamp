'''
Created on Nov 12, 2013

@author: emilymw
Copyright (c) 2013 by Cisco Systems
'''
import translator
from base.simpletype import SimpleType
from base.dmobject import DMObject
from base.dmlist import DMList
from base.compositetype import CompositeType
from translator.state_type import State
from translator.base.dmboolean import DMBoolean
import asaio.cli_interaction as cli_interaction
from translator.structured_cli import StructuredCommand
import utils.util as util

class BridgeGroupIntfs(DMList):
    'Container of BridgeGroupIntf'
    def __init__(self):
        DMList.__init__(self, name='BridgeGroupIntf', asa_key='interface BVI', child_class=BridgeGroupIntf)

    def is_my_cli(self, cli):
        if not isinstance(cli, StructuredCommand):
            return False

        return cli.command.startswith('interface BVI') # check if it is a BVI interface

class BridgeGroupIntf(CompositeType):
    'Model for "interface BVI" CLI'
    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='interface BVI%(bvi_id)s');
        self.register_child(IPv4Addr('ipv4_address'))
        self.register_child(DMList(name='ipv6_address_with_prefix', child_class=IPv6Addr, asa_key ='ipv6 address'))
        self.register_child(IPv6Enable('ipv6_enable'))
        self.register_child(IPv6NDDad('ipv6_nd_dad_attempts'))
        self.register_child(IPv6NDNsInterval('ipv6_nd_ns_interval'))
        self.register_child(IPv6NDReachable('ipv6_nd_reachable_time'))
        self.member1 = BridgeGroupMember()
        self.member2 = BridgeGroupMember()
        self.response_parser = cli_interaction.ignore_info_response_parser

    def get_vlan_label_from_connector(self, name):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(name)
        return connector.get_vlan_interface()

    def is_bvi_id_changed(self):
        if self.has_ifc_delta_cfg():
            cfg = self.delta_ifc_cfg_value.get('value')
            for delta_ifc_key, value in cfg.iteritems():
                kind, key, instance = delta_ifc_key
                if key == 'bvi_id':
                    return value['state'] == State.MODIFY
        return False

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if self.has_ifc_delta_cfg():
            bvi_id = self.get_cli().split('interface BVI')[1]
            intf1 = self.get_vlan_label_from_connector('internal')
            intf2 = self.get_vlan_label_from_connector('external')
            state = self.get_action()

            if state == State.DESTROY and \
                isinstance(self.ifc_key, str) and self.ifc_key.startswith('bvi'):
                '''
                In non audit case, would need to remove member.
                During audit, the sub CLIs like member would be taken care off by the connector
                with 'clear config interface ...'  but below will generate 'no bridge-group ...'
                
                '''
                self.member1.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, state, intf1, bvi_id)
                self.member2.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, state, intf2, bvi_id)

            CompositeType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

            if state == State.CREATE or self.is_bvi_id_changed():
                self.member1.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, state, intf1, bvi_id)
                self.member2.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, state, intf2, bvi_id)

    def create_asa_key(self):
        return self.get_cli()

class IPv4Addr(SimpleType):
    'Model after "ip address ipv4_address netmask" sub-command'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_gen_template='ip address %s')

    def create_asa_key(self):
        return self.get_cli()

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        value = self.get_value()
        if '.' in value: #ipv4 address
            value = ' '.join(value.split('/'))
        return self.asa_gen_template % value

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because the IPv4 address is entered as an address and netmask tuple'
        return '/'.join(cli.split()[1:])

class IPv6Enable(DMBoolean):
    'Model after "ipv6 enable'
    def __init__(self, instance):
        DMBoolean.__init__(self, ifc_key = instance, asa_key = 'ipv6 enable', on_value="enable")
        self.cli_key = 'enable'

class IPv6NDDad(SimpleType):
    'Model after  "ipv6 nd dad attempts <0-600>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'ipv6 nd dad attempts', \
                            asa_gen_template='ipv6 nd dad attempts %s')

class IPv6NDNsInterval(SimpleType):
    'Model after  "ipv6 nd ns-interval <1000-3600000 ms>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'ipv6 nd ns-interval', \
                            asa_gen_template='ipv6 nd ns-interval %s')

class IPv6NDReachable(SimpleType):
    'Model after  "ipv6 nd reachable-time <0-3600000 ms>'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_key = 'ipv6 nd reachable-time', \
                            asa_gen_template='ipv6 nd reachable-time %s')

class IPv6Addr(SimpleType):
    'Model after "ipv6 address ipv6_address/prefix " subcommand'
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_gen_template='ipv6 address %s')

    def create_asa_key(self):
        return self.get_cli()

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        assert self.has_ifc_delta_cfg()
        addr = util.normalize_ipv6_address(self.delta_ifc_cfg_value['value'])  
        result = 'ipv6 address ' + addr
        return ' '.join(result.split())

class BridgeGroupMember(DMObject):
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        pass

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Handled by Connector'
        pass

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, state, intf, bvi):
        if state == State.NOCHANGE:
            return
        self.mode_command = 'interface %s' % intf
        if state == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack, 'no bridge-group %s'  % bvi)
        if state in [State.CREATE, State.MODIFY]:
            self.generate_cli(asa_cfg_list, 'bridge-group %s' % bvi)
