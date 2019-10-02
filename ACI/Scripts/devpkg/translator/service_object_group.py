'''
Created on Oct 25, 2013

Copyright (c) 2013 by Cisco Systems
@author: dli
'''

import re
from base.simpletype import SimpleType
from base.dmlist import DMList
from base.compositetype import CompositeType, Description
from state_type import Type
from utils.util import ifcize_param_dict
from object_group import ObjectGroupList
from validators import ICMPValidator, ProtocolValidator, TCPUDPValidator
from network_object_group import idempotent_response_parser

class ServiceObjectGroups(ObjectGroupList):
    'Container of ServiceObjectGroup'
    def __init__(self):
        """We are not interested in 'object-group service <name> [tcp|udp|tcp-udp]' variants, as they are legacy.
        """
        DMList.__init__(self, name='ServiceObjectGroup',
                        asa_key=re.compile('^object-group service \S+$'),
                        child_class=ServiceObjectGroup)

class ServiceObjectGroup(CompositeType):
    """ Model for 'object-group service <name>' CLI.
    We are not interested in 'object-group service <name> [tcp|udp|tcp-udp]' variants, as they are legacy.
    """
    def __init__(self, instance):
        SimpleType.__init__(self, ifc_key = instance, asa_gen_template='object-group service %(name)s');
        self.register_child(Description())
        children = [# ifc_key              child_class      asa_key
                    ('protocol_type',      ProtocolObject, '^service-object \S+$'),
                    ('object_name',        ObjectObject,   '^service-object object'),
                    ('tcp',                TCPObject,      '^service-object tcp '),
                    ('udp',                UDPObject,      '^service-object udp '),
                    ('tcp-udp',            TCPUDPObject,   '^service-object tcp-udp'),
                    ('icmp',               ICMPObject,     '^service-object icmp '),
                    ('icmp6',              ICMP6Object,    '^service-object icmp6'),
                    ('object_group_name',  GroupObject,    '^group-object'),
        ]
        for ifc_key, child_class, asa_key in children:
            self.register_child(DMList(ifc_key, child_class, re.compile(asa_key)))

    def create_asa_key(self):
        return self.get_cli()

class _ServiceObject(SimpleType):
    'base class for service-object and group-object sub-command'
    def __init__(self, ifc_key, asa_gen_template, allow_modify = False):
        SimpleType.__init__(self, ifc_key = ifc_key, asa_gen_template = asa_gen_template)
        self.allow_modify = allow_modify

    def create_asa_key(self):
        return self.get_cli()

    def generate_cli(self, asa_cfg_list, cli):
        """
        Override the default implementation to make the modify and delete CLI idempotent.
        That is issuing the CLI multiple times result in the same behavior in the running-config
        without the need to report error.
        """
        SimpleType.generate_cli(self, asa_cfg_list, cli, response_parser = idempotent_response_parser)


class ProtocolObject(_ServiceObject, ProtocolValidator):
    '''Model after 'service-object \S+$' object'''
    def __init__(self, instance):
        _ServiceObject.__init__(self, ifc_key = instance, asa_gen_template='service-object %s')

class GroupObject(_ServiceObject):
    'Model after "group-object" sub-command'
    def __init__(self, instance):
        _ServiceObject.__init__(self, ifc_key = instance, asa_gen_template='group-object %s')

class ObjectObject(_ServiceObject):
    'Model after "service-object object" sub-command'
    def __init__(self, instance):
        _ServiceObject.__init__(self, ifc_key = instance, asa_gen_template='service-object object %s')

class ICMPSubCommand(_ServiceObject, ICMPValidator):
    'Base class for "service-object icmp " "service-object icmp6" sub-commands'
    def __init__(self, instance, type, allow_modify = False):
        '@param type: "icmp" or "icmp6"'
        _ServiceObject.__init__(self, ifc_key = instance,
                                asa_gen_template = 'service-object ' + type + ' %(type)s %(code)s',
                                allow_modify = allow_modify)
        ICMPValidator.__init__(self, type)
        self.defaults={'code': ''}

    def create_asa_key(self):
        'The whole CLI makes up the key'
        return self.get_cli()

    def parse_multi_parameter_cli(self, cli):
        '''Override the default implementation in case the CLI does not match asa_gen_template due to optional
        parameter
        '''
        result = SimpleType.parse_multi_parameter_cli(self, cli)
        if not result:
            result = SimpleType.parse_multi_parameter_cli(self, cli,
                                                          alternate_asa_gen_template = ' '.join(self.asa_gen_template.split()[:3]))
        return result

class ICMPObject(ICMPSubCommand):
    'Model after "service-object icmp " sub-command'
    def __init__(self, instance):
        ICMPSubCommand.__init__(self, instance, type =  'icmp')

class ICMP6Object(ICMPSubCommand):
    'Model after "service-object icmp6" sub-command'
    def __init__(self, instance):
        ICMPSubCommand.__init__(self, instance, type =  'icmp6')

class TCPUDPSubCommand(_ServiceObject, TCPUDPValidator):
    'Base class for "service-object [tcp|udp|tcp-udp]" sub-commands'
    def __init__(self, instance, type, allow_modify = False):
        _ServiceObject.__init__(self, ifc_key = instance,
                                asa_gen_template = 'service-object ' + type + ' %(source)s %(destination)s',
                                allow_modify = allow_modify)
        TCPUDPValidator.__init__(self, type)

    def get_state_for_entry(self, name):
        '''
        @param name: str, the name of a entry in the IFC configuration dictionary
        @return the value "state" in the IFC configuration dictionary for the named field
        @todo move this method to DMObject.
        '''
        value = self.delta_ifc_cfg_value['value'].get((Type.PARAM, name, ''))
        if not value:
            value = self.delta_ifc_cfg_value['value'].get((Type.FOLDER, name, ''))
        if value:
            return value['state']
        else:
            return None

    def get_cli(self):
        'Override the default implementation to take care of the variations of the command'
        assert self.has_ifc_delta_cfg()
        value = self.get_value()
        for name in ['source', 'destination']:
            #@todo self.get_state_for_entry(name) not there
            if value.get(name):
                folder = value[name]
                op = folder.get('operator')
                value[name] = ' '.join([name, op, folder.get('low_port'),
                                        folder.get('high_port')  if 'range' == op.lower() else ''])
            else:
                value[name] = ''

        return ' '.join((self.asa_gen_template % value).split())

    def parse_cli(self, cli):
        'Override the default to handle variations of the command'
        result = {}
        parameters = ' '.join(cli.split()[2:])
        if not parameters:# cli is of the form 'service-object <type>'
            return ifcize_param_dict(result)

        def parse_parameters(items):
            folder = items[0]
            result[folder] = {}
            result[folder]['operator'] = items[1]
            result[folder]['low_port'] = items[2]
            if len(items) == 4:
                result[folder]['high_port'] = items[3]

        pattern = '(source .+) (destination .+)'
        match = re.compile(pattern).match(parameters)
        if match:#cli is of the form 'service-object <type> source <value> destination <value>'
            parse_parameters(match.group(1).split())
            parse_parameters(match.group(2).split())
        else: #of the form 'service-object <type> [source|destination] <value>'
            parse_parameters(parameters.split())
        return ifcize_param_dict(result)

class TCPObject(TCPUDPSubCommand):
    'Model after "service-object tcp" sub-command'
    def __init__(self, instance):
        TCPUDPSubCommand.__init__(self, instance, type = 'tcp')

class UDPObject(TCPUDPSubCommand):
    'Model after "service-object udp" sub-command'
    def __init__(self, instance):
        TCPUDPSubCommand.__init__(self, instance, type =  'udp')

class TCPUDPObject(TCPUDPSubCommand):
    'Model after "service-object tcp-udp" sub-command'
    def __init__(self, instance):
        TCPUDPSubCommand.__init__(self, instance, type = 'tcp-udp')
