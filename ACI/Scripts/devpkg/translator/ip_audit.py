'''
Created on Oct 2, 2013

@author: richauha

Copyright (c) 2013 by Cisco Systems
'''
from base.dmobject import DMObject
from base.simpletype import SimpleType
from translator.state_type import State

class IPAudit(DMObject):
    '''
    This is for basic ip audit configurations.
    IP Audit section correspond to ASDM's Firewall>Advanced>IP Audit screen.
    '''
    def __init__(self):
        '''
        Constructor
        '''
        DMObject.__init__(self, ifc_key = IPAudit.__name__, asa_key = 'ip audit')
        self.register_child(IPAuditObj(ifc_key='IPAuditAttack', asa_key='ip audit attack', asa_gen_template='ip audit attack action %s'))
        self.register_child(IPAuditObj(ifc_key='IPAuditInfo', asa_key='ip audit info', asa_gen_template='ip audit info action %s'))
        
class IPAuditObj(SimpleType):
    def __init__(self, ifc_key, asa_key, asa_gen_template):
        SimpleType.__init__(self, ifc_key, asa_key, asa_gen_template)
    
    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Override default implementation to deal with different CLI for no commands.'
        tmp_no_asa_cfg_stack = []
        result = SimpleType.ifc2asa(self, tmp_no_asa_cfg_stack, asa_cfg_list)
        if tmp_no_asa_cfg_stack:
            action = self.get_action()
            if action == State.DESTROY and self.is_removable:
                if self.get_asa_key() == 'ip audit info':
                    self.generate_cli(no_asa_cfg_stack, 'no ip audit info')
                else:
                    self.generate_cli(no_asa_cfg_stack, 'no ip audit attack')
        return result

    def parse_single_parameter_cli(self, cli):
        'Override the default implementation by returning 4th to last tokens from the CLI as the value '
        return ' '.join(cli.split()[4:])

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        """'Override the default implementation to have the value normalized with respect to the CLI,
        i.e. 'drop reset alarm' is seen the same as 'alarm drop reset'
        """
        delta_ifc_cfg_value['value'] = ' '.join(sorted(delta_ifc_cfg_value['value'].lower().split()))
        return SimpleType.populate_model(self, delta_ifc_key, delta_ifc_cfg_value)
