#
# Copyright (c) 2013 by Cisco Systems, Inc.
#
'''
Created on Jun 28, 2013

@author: feliu

This is the logging class.

'''

from translator.base.dmobject import DMObject
from translator.base.dmlist import DMList
from translator.base.simpletype import SimpleType
import utils.util as util
import asaio.cli_interaction as cli_interaction
from translator.base.dmboolean import DMBoolean
from translator.state_type import Type, State

class LoggingConfig(DMObject):
    '''
    This class represents the holder of all logging configuration.
    '''
    def __init__(self):
        DMObject.__init__(self, LoggingConfig.__name__)

        ifc_asa_keys = (
                        ("facility",                "logging facility"),
                        ("buffered_level",          "logging buffered"),
                        ("buffer_size",             "logging buffer-size"),
                        ("flash_maximum_allocation","logging flash-maximum-allocation"),
                        ("flash_minimum_free",      "logging flash-minimum-free")
                        )
        for (ifc, asa) in ifc_asa_keys:
            self.register_child(SimpleType(ifc, asa, is_removable=True,
                                response_parser=cli_interaction.ignore_warning_response_parser))

        self.register_child(LoggingTrap())
        ifc_asa_keys_boolean_type = (
                        ("enable_logging",          "logging enable"),
                        ("standby",                 "logging standby"),
                        ("flash_bufferwrap",        "logging flash-bufferwrap"),
                        ("permit_hostdown",         "logging permit-hostdown")
                        )
        for (ifc, asa) in ifc_asa_keys_boolean_type:
            self.register_child(DMBoolean(ifc, asa, on_value="enable",
                                response_parser=cli_interaction.ignore_warning_response_parser))

        self.register_child(DMList('logging_host', LoggingHost, asa_key='logging host'))
        self.register_child(DMList('logging_message', LoggingMessage, asa_key='logging message'))
        self.response_parser = cli_interaction.ignore_warning_response_parser

class LoggingTrap(SimpleType):
    def __init__(self):
        SimpleType.__init__(self, ifc_key='trap_level', asa_key='logging trap',
                            response_parser=cli_interaction.ignore_warning_response_parser)

    def get_cli(self):
        '''Generate the CLI for this single logging trap config.
        '''
        cli = SimpleType.get_cli(self).lower()
        trap_level_list = [('0', 'emergencies'),
                           ('1', 'alerts'),
                           ('2', 'critical'),
                           ('3', 'errors'),
                           ('4', 'warnings'),
                           ('5', 'notifications'),
                           ('6', 'informational'),
                           ('7', 'debugging')]
        for item in trap_level_list:
            (num_level, desc_level) = item
            cli = cli.replace(num_level, desc_level)
        return cli

class LoggingHost(SimpleType):
    def __init__(self, name):
        SimpleType.__init__(self, name, is_removable = True,
                            asa_gen_template='logging host %(interface)s %(ip)s',
                            response_parser = cli_interaction.ignore_warning_response_parser)

    def get_cli(self):
        '''Generate the CLI for this single logging host config.
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        protocol_port = config.get('protocol_port', '')
        secure = config.get('secure')
        secure = " secure" if secure == 'enable' else ''
        emblem = config.get('emblem')
        emblem = " format emblem" if emblem == 'enable' else ''
        result = SimpleType.get_cli(self)
        result += ' ' + protocol_port + secure + emblem
        result = result.lower()
        # This is how ASA saves them
        result = result.replace('tcp/', '6/')
        result = result.replace('udp/', '17/')
        return ' '.join(result.split())

    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return self.asa_gen_template % value + ' '

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional parameter
        '''
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of mandatory parameters is 4, i.e. 'logging host management 2.2.2.2'
        if len(tokens) == 4:
            return result # no optional parameter

        for name  in ['secure', 'protocol_port', 'emblem']:
            result[(Type.PARAM, name, '')] = {'state': State.NOCHANGE, 'value': ''}

        option = tokens[4:]
        if 'secure' in option: # e.g. "logging host mgmt 2.2.2.2 secure
            result[Type.PARAM, 'secure', '']['value'] = 'enable'
        if 'emblem'in option: # e.g. "logging host mgmt 2.2.2.2 format emblem
            result[Type.PARAM, 'emblem', '']['value'] = 'enable'
        if '/' in option[0]: # e.g. "logging host mgmt 2.2.2.2 6/1471'
            result[Type.PARAM, 'protocol_port', '']['value'] = option[0]
        return result


class LoggingMessage(SimpleType):
    def __init__(self, name):
        SimpleType.__init__(self, name, is_removable=True,
                            asa_gen_template='logging message %(message)s',
                            response_parser = cli_interaction.ignore_warning_response_parser)

    def get_cli(self):
        '''Generate the CLI for this single logging message config.
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        level = config.get('level')
        level = ' level ' + level if level else ''
        return 'logging message %(message)s' % config + level

    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return 'logging message %(message)s' % value

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional parameter
        '''
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of mandatory parameters is 3, i.e. 'logging message 106015'
        if len(tokens) == 3:
            return result # no optional parameter

        result[(Type.PARAM, 'level', '')] = {'state': State.NOCHANGE, 'value': ''}

        option = tokens[3:]
        if 'level' in option: # e.g. "logging message 106015 level critical
            result[Type.PARAM, 'level', '']['value'] = option[1]
        return result
