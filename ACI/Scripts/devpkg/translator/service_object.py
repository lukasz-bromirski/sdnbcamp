'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''
from base.simpletype import SimpleType
from base.dmlist import DMList
from network_object import _ObjectNetwork, _ObjectNetworks
import service_object_group
from validators import ProtocolValidator

class _ObjectServices(_ObjectNetworks):
    'Base class for the containers'
    def __init__(self, name, child_class, asa_sub_key):
        DMList.__init__(self, name, child_class, asa_key = 'object service')
        self.asa_sub_key = asa_sub_key

class ICMP4Objects(_ObjectServices):
    'Container for ICMP4Object'
    def __init__(self):
        _ObjectServices.__init__(self, 'ICMPObject', ICMP4Object, asa_sub_key = 'service icmp ')
        #@note: keep the space after 'icmp' in asa_sub_key to differentiate it from icmp6

class ICMP6Objects(_ObjectServices):
    'Container for ICMP6Object'
    def __init__(self):
        _ObjectServices.__init__(self, 'ICMP6Object', ICMP6Object, asa_sub_key = 'service icmp6')


class ProtocolObjects(_ObjectServices):
    'Container for ProtocolObject'
    def __init__(self):
        'Anything other service other than icmp, icmp6, tcp, udp'
        _ObjectServices.__init__(self, 'ProtocolObject', ProtocolObject, asa_sub_key = 'service (?!icmp|tcp|udp)')

class TCPObjects(_ObjectServices):
    'Container for TCPObject'
    def __init__(self):
        _ObjectServices.__init__(self, 'TCPObject', TCPObject, asa_sub_key = 'service tcp')

class UDPObjects(_ObjectServices):
    'Container for TCPObject'
    def __init__(self):
        _ObjectServices.__init__(self, 'UDPObject', UDPObject, asa_sub_key = 'service udp')

class _ObjectService(_ObjectNetwork):
    '''Base class 'object service' CLI object. This is the base type for all rest classes in this module.
    Re-use object_network._ObjectNetwork, the only difference is the asa_gen_template.
    '''
    def __init__(self, name):
        _ObjectNetwork.__init__(self, name)
        self.asa_gen_template = 'object service %(name)s';

class ICMPSubComnand(service_object_group.ICMPSubCommand):
    'Base class for service icmp/icmp6 sub-commands'
    def __init__(self, type):
        'Override the default implementation to use different asa CLI prefix'
        service_object_group.ICMPSubCommand.__init__(self, 'icmp', type, allow_modify = True)
        self.asa_gen_template = 'service ' + type + ' %(type)s %(code)s'

class ICMP4Object(_ObjectService):
    '''Model after 'object service\n service icmp ' object
    '''
    def __init__(self, name):
        _ObjectService.__init__(self, name)
        self.register_child(ICMPSubComnand('icmp'))

class ICMP6Object(_ObjectService):
    '''Model after 'object service\n service icmp6' object
    '''
    def __init__(self, name):
        _ObjectService.__init__(self, name)
        self.register_child(ICMPSubComnand('icmp6'))

class ProtocolSubCommand(SimpleType, ProtocolValidator):
    '''Model after 'service \d+' sub-command
    '''
    def __init__(self):
        SimpleType.__init__(self, ifc_key = 'protocol_type', asa_key = 'service')

class ProtocolObject(_ObjectService):
    '''Model after 'object service\n service \d+' object
    '''
    def __init__(self, name):
        _ObjectService.__init__(self, name)
        self.register_child(ProtocolSubCommand())

class TCPUDPSubComnand(service_object_group.TCPUDPSubCommand):
    'Base class for service tcp/udp sub-commands'
    def __init__(self, instance):
        'Override the default implementation to use different asa CLI prefix'
        service_object_group.TCPUDPSubCommand.__init__(self, instance, instance, allow_modify= True)
        self.asa_gen_template = 'service ' + instance + ' %(source)s %(destination)s'

class TCPObject(_ObjectService):
    '''Model after 'object service\n service tcp object
    '''
    def __init__(self, name):
        _ObjectService.__init__(self, name)
        self.register_child(TCPUDPSubComnand('tcp'))

class UDPObject(_ObjectService):
    '''Model after 'object service\n service icmp6' object
    '''
    def __init__(self, name):
        _ObjectService.__init__(self, name)
        self.register_child(TCPUDPSubComnand('udp'))
