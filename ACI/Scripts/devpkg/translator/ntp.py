'''
Created on Oct 28, 2013

@author: richauha

Copyright (c) 2013 by Cisco Systems
'''
from translator.base.dmlist import DMList
from translator.base.dmobject import DMObject
from base.simpletype import SimpleType
from translator.base.dmboolean import DMBoolean
import utils.util as util
from translator.state_type import Type, State

class NTP(DMObject):
    'Container of NTP'
    def __init__(self):
        DMObject.__init__(self, NTP.__name__)
        self.register_child(DMList('NTPServer', NTPObj, asa_key='ntp server'))
        self.register_child(DMList(name='NTPTrustedKey',    child_class = NTPTrustedKey,    asa_key = 'ntp trusted-key'))
        self.register_child(DMBoolean(ifc_key='NTPAuthenticate', asa_key='ntp authenticate', on_value="enable"))
        self.register_child(DMList(name='NTPAuthenticationKey',    child_class = NTPAuthenticationKey,    asa_key = 'ntp authentication-key'))
        

class NTPObj(SimpleType):
    'Model for "ntp server" CLI'

    def __init__(self, name):
        SimpleType.__init__(self, name, asa_gen_template='ntp server %(server)s')

    def get_cli(self):
        '''Generate the CLI for ntp server config.
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        key = config.get('key')
        key = ' key ' + key if key else ''
        prefer = config.get('prefer')
        prefer = ' prefer ' if prefer == 'enable' else ''
        return 'ntp server %(server)s' % config + key + prefer
        
    def create_asa_key(self):
        '''Create the the asa key identifies this object
        @return str
        '''
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        return 'ntp server %(server)s' % value

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional parameter
        '''
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        'Take care of the optional parameters'
        tokens = cli.split()

        # The number of mandatory parameters is 3, i.e. 'ntp server 1.1.1.1'
        if len(tokens) == 3:
            return result # no optional parameter

        for name  in ['key', 'prefer']:
            result[(Type.PARAM, name, '')] = {'state': State.NOCHANGE, 'value': ''}

        option = tokens[3:]
        if 'key' in option: # e.g. "ntp server 1.1.1.1 key 11
            result[Type.PARAM, 'key', '']['value'] = option[1]
        if 'prefer' in option: # e.g. "ntp server 1.1.1.1 prefer
            result[Type.PARAM, 'prefer', '']['value'] = 'enable'
        return result
    
class NTPTrustedKey(SimpleType):
    
    'Model for "ntp trusted-key" CLI'
    def __init__(self, name):
        SimpleType.__init__(self, name, asa_gen_template='ntp trusted-key %s')
    
    def create_asa_key(self):
        return self.get_cli()
    
class NTPAuthenticationKey(SimpleType):
    
    'Model for "ntp authentication-key" CLI'
    def __init__(self, name):
        SimpleType.__init__(self, name, is_removable = True,
                            asa_gen_template='ntp authentication-key %(key_number)s md5 %(key)s')
    
