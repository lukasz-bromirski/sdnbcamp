'''
Created on Oct 22, 2013

@author: dli
Copyright (c) 2013 by Cisco Systems
'''
from base.simpletype import SimpleType
from base.dmlist import DMList
from base.compositetype import CompositeType, Description
from object_group import ObjectGroupList
from validators import IPAddressValidator, IPAddressSubnetValidator

class NetworkObjectGroups(ObjectGroupList):
    'Container of NetworkObjectGroup'
    def __init__(self):
        DMList.__init__(self, name='NetworkObjectGroup', asa_key='object-group network', child_class=NetworkObjectGroup)

class NetworkObjectGroup(CompositeType):
    'Model for "object-group network" CLI'
    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='object-group network %(name)s');
        self.register_child(Description())
        self.register_child(DMList(name='host_ip_address',    child_class = HostObject,    asa_key = 'network-object host'))
        self.register_child(DMList(name='object_name',        child_class = ObjectObject,  asa_key = 'network-object object'))
        self.register_child(DMList(name='network_ip_address', child_class = NetworkObject, asa_key = 'network-object'))
        self.register_child(DMList(name='object_group_name',  child_class = GroupObject,   asa_key = 'group-object'))

    def create_asa_key(self):
        return self.get_cli()

def idempotent_response_parser(response):
    """
    Response parser to ignore response from the ASA when duplicates is added, as well
    as delete non-existing entries.
    """
    if not response:
        return
    if response.strip().endswith('failed; object already exists'):
        return
    if response.strip() == 'obj does not exist in this group':
        return
    return response

class _NetworkObject(SimpleType):
    'base class for network-object and group-object sub-command'
    def __init__(self, ifc_key, asa_gen_template):
        SimpleType.__init__(self, ifc_key = ifc_key, asa_gen_template = asa_gen_template)

    def create_asa_key(self):
        return self.get_cli()

    def generate_cli(self, asa_cfg_list, cli):
        """
        Override the default implementation to make the modify and delete CLI idempotent.
        That is issuing the CLI multiple times result in the same behavior in the running-config
        without the need to report error.
        """
        SimpleType.generate_cli(self, asa_cfg_list, cli, response_parser = idempotent_response_parser)

class HostObject(_NetworkObject, IPAddressValidator):
    'Model after "network-object host" sub-command'
    def __init__(self, instance):
        _NetworkObject.__init__(self, ifc_key = instance, asa_gen_template='network-object host %s')

class ObjectObject(_NetworkObject):
    'Model after "network-object object" sub-command'
    def __init__(self, instance):
        _NetworkObject.__init__(self, ifc_key = instance, asa_gen_template='network-object object %s')

class NetworkObject(_NetworkObject, IPAddressSubnetValidator):
    'Model after "network-object ipv4_address netmask" and "network-object ipv6_address/prefix_length" sub-command'
    def __init__(self, instance):
        _NetworkObject.__init__(self, ifc_key = instance, asa_gen_template='network-object %s')

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        value = self.get_value()
        if '.' in value: #ipv4 address
            value = ' '.join(value.split('/'))
        return self.asa_gen_template % value

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because the IPv4 network address is entered as an address and netmask tuple'
        return '/'.join(cli.split()[1:])

class GroupObject(_NetworkObject):
    'Model after "group-object" sub-command'
    def __init__(self, instance):
        _NetworkObject.__init__(self, ifc_key = instance, asa_gen_template='group-object %s')
