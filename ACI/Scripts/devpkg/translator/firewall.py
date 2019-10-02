'''
Created on Oct 17, 2013
Copyright (c) 2013 by Cisco Systems

@author: dli
'''
from base.dmlist import DMList
from base.dmobject import DMObject
from connector import ExIntfConfigRelFolder, InIntfConfigRelFolder, Connectors, Connector
from connector import InIPv6EnforceEUI64, ExIPv6EnforceEUI64
from bridge_group_interface import BridgeGroupIntfs
from static_route import IntStaticRoute, ExtStaticRoute
from rule.access_rule import AccessGroupList
from rule.nat_rule import NATRuleList, NATRuleDeployment
from service_policy import ExtConnectorServicePolicyContainer, IntConnectorServicePolicyContainer
from state_type import State, Type

class Firewalls(DMList):
    'Container for Firewall translator, one per graph'
    def __init__(self):
        DMList.__init__(self, Firewall.__name__, Firewall)

    def get_translator(self, cli):
        'Override the default implementation'
        if not self.is_my_cli(cli):
            return

        'Find the translator from its children'
        result = None
        for child in self.children.values():
            if 'get_translator' in dir(child):
                result = child.get_translator(cli)
                if result:
                    break
        if result:
            return result
        'Create a child that is to generate "no" cli, by the invocation of child.diff_ifc_asa'
        '@todo more complex than what you have now, based on connector'
#         result = self.child_class(cli)
#         self.register_child(result)
        return result

    def is_my_cli(self, cli):
        'Create FW instance based on Connector interface CLI during audit'
        fw_name = Connectors.get_connector_fw_name(cli, self.get_top().is_virtual())
        if fw_name:
            self.create_firewall1(fw_name)
        'Override the default implementation'
        cmd_str = cli if isinstance(cli, basestring) else cli.command
        '@todo go through the children of Firewall to build up cli_prefixes'
        cli_prefixes = ['route ', 'ipv6 route ', 'access-group ']
        return any(lambda x: cmd_str.startswith(x) for x in cli_prefixes)

    def create_firewall1(self, name):
        if not name in self.children:
            self.register_child(Firewall(name))
            DMList.create_missing_ifc_delta_cfg(self)

    def get_firewall(self, fw_name):
        'Get the firewall object by name'
        for fw in self.children.itervalues():
            if fw.ifc_key == 'FW':
                'Replace FW with first firewall instance'
                self.unregister_child(fw)
                ancestor = self.get_ifc_delta_cfg_ancestor()
                del ancestor.delta_ifc_cfg_value['value'][fw.delta_ifc_key]
                fw.ifc_key = fw_name
                fw.delta_ifc_key = (Type.FUNC, 'Firewall', fw_name)
                self.register_child(fw)
                return fw
            if fw.ifc_key == fw_name:
                'Return existing firewall with matching firewall name'
                return fw  
        return self.create_firewall(fw_name)

    def create_firewall(self, fw_name):
        'Create a firewall config during audit'
        self.register_child(Firewall(fw_name))
        child = self.get_child(fw_name)
        child.delta_ifc_key = (Type.FUNC, 'Firewall', fw_name)
        child.delta_ifc_cfg_value =  {'state': State.DESTROY, 'value':{}}
        return child


class Firewall(DMObject):
    '''
    This is the function configuration of ASA, assuming the name of "MFunc" element in the device_specifcation is "Firewall".
    Add firewall related configuration objects by call self.register_child(dmobj) in
    the constructor as it is done in DeviceModel.__init(self)__.
    '''
    def __init__(self, instance):
        DMObject.__init__(self, instance)
        self.register_child(ExIntfConfigRelFolder())
        self.register_child(InIntfConfigRelFolder())
        self.register_child(Connectors('CONN', Connector))
        self.register_child(BridgeGroupIntfs())
        self.register_child(NATRuleList())
        self.register_child(NATRuleDeployment()) # Must follow NATRuleList
        self.register_child(AccessGroupList('ExtAccessGroup', 'external'))
        self.register_child(AccessGroupList('IntAccessGroup', 'internal'))
        self.register_child(IntStaticRoute())
        self.register_child(ExtStaticRoute())
        self.register_child(InIPv6EnforceEUI64())
        self.register_child(ExIPv6EnforceEUI64())
        self.register_child(IntConnectorServicePolicyContainer())
        self.register_child(ExtConnectorServicePolicyContainer())

    def get_firewall_name(self):
        'Return the firewall name.  Called by Connector.get_nameif()'
        if self.has_ifc_delta_cfg():
            type, key, name = self.delta_ifc_key
            return name
        else:
            return None

    def get_connector(self, connector_name):
        for conn in self.get_child('CONN').children.itervalues():
            if 'conn_type' in conn.__dict__ and conn.conn_type == connector_name:
                return conn

    def create_missing_ifc_delta_cfg(self):
        '''Override the default to take care of the way self.delta_ifc_key is created
        '''
        if  not self.has_ifc_delta_cfg():
            '@todo isolate changes to key creation'
            self.delta_ifc_key = Type.FOLDER, Firewall.__name__, self.ifc_key,
            self.delta_ifc_cfg_value = {'state': State.NOCHANGE, 'value': {}}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            if ancestor:
                ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
        for child in self.children.values():
            child.create_missing_ifc_delta_cfg()
