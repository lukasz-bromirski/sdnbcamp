'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''
import re
from base.simpletype import SimpleType
from base.dmlist import DMList
from base.compositetype import CompositeType, Description
from validators import IPAddressValidator, IPAddressRangeValidator, IPAddressSubnetValidator, VersionFQDNValidator

class _ObjectNetworks(DMList):
    'Base class for the containers'
    def __init__(self, name, child_class, asa_sub_key):
        DMList.__init__(self, name, child_class, asa_key = 'object network')
        self.asa_sub_key = asa_sub_key

    def is_my_cli(self, cli):
        if isinstance(cli, str):
            return False # not handled by us
        if not cli.command.startswith(self.asa_key):
            return False
        return any(re.compile(self.asa_sub_key).match(str(cmd).strip()) for cmd in  cli.sub_commands)

class HostObjects(_ObjectNetworks):
    'Container for HostObject'
    def __init__(self):
        _ObjectNetworks.__init__(self, 'HostObject', HostObject, asa_sub_key = 'host')

class RangeObjects(_ObjectNetworks):
    'Container for RangeObject'
    def __init__(self):
        _ObjectNetworks.__init__(self, 'RangeObject', RangeObject, asa_sub_key = 'range')

class SubnetObjects(_ObjectNetworks):
    'Container for SubnetObject'
    def __init__(self):
        _ObjectNetworks.__init__(self, 'SubnetObject', SubnetObject, asa_sub_key = 'subnet')

class FQDNObjects(_ObjectNetworks):
    'Container for FQDNObject'
    def __init__(self):
        _ObjectNetworks.__init__(self, 'FQDNObject', FQDNObject, asa_sub_key = 'fqdn')

class _ObjectNetwork(CompositeType):
    '''Base class 'object network' CLI object. This is the base type for all rest classes in this module
    '''
    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template='object network %(name)s');
        self.register_child(Description())

    def create_asa_key(self):
        return self.get_cli()


class HostSubCommand(SimpleType, IPAddressValidator):
    'Model after "host" sub-command'
    def __init__(self):
        SimpleType.__init__(self, ifc_key='host_ip_address', asa_key = 'host')

class HostObject(_ObjectNetwork):
    '''Model after 'object network\n host' object
    '''
    def __init__(self, name):
        _ObjectNetwork.__init__(self, name);
        self.register_child(HostSubCommand())

class SubnetSubCommand(SimpleType, IPAddressSubnetValidator):
    'Model after "subnet" sub-command'
    def __init__(self):
        SimpleType.__init__(self, ifc_key='network_ip_address', asa_key = 'subnet')

    def get_cli(self):
        'Override the default implementation to take care / delimiter'
        value = self.get_value()
        if '.' in value: #ipv4 address
            value = ' '.join(value.split('/'))
        return self.asa_gen_template % value

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because the IPv4 network address is entered as an address and netmask tuple'
        return '/'.join(cli.split()[1:])

class SubnetObject(_ObjectNetwork):
    '''Model after 'object network\n subnet' object
    '''
    def __init__(self, name):
        _ObjectNetwork.__init__(self, name);
        self.register_child(SubnetSubCommand())

class RangeSubCommand(SimpleType, IPAddressRangeValidator):
    'Model after "range" sub-command'
    def __init__(self):
        SimpleType.__init__(self, ifc_key='ip_address_range', asa_key = 'range')

    def get_cli(self):
        'Override the default implementation to take care "-" delimiter'
        value = self.get_value()
        if '.' in value: #ipv4 address
            value = ' '.join(value.split('-'))
        return self.asa_gen_template % value

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because to use "-" as the delimiter'
        return '-'.join(cli.split()[1:])

class RangeObject(_ObjectNetwork):
    '''Model after 'object network\n range" object
    '''
    def __init__(self, name):
        _ObjectNetwork.__init__(self, name);
        self.register_child(RangeSubCommand())

class FqdnSubCommand(SimpleType, VersionFQDNValidator):
    "Model after 'fqdn' sub-command. The value is in the form of: {v4|v6} <fqdn-string>"
    def __init__(self):
        SimpleType.__init__(self, ifc_key='fqdn', asa_key = 'fqdn')

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation because to use the multiple parameters'
        return ' '.join(cli.split()[1:])

class FQDNObject(_ObjectNetwork):
    '''Model after 'object network\n fqdn" object
    '''
    def __init__(self, name):
        _ObjectNetwork.__init__(self, name);
        self.register_child(FqdnSubCommand())
