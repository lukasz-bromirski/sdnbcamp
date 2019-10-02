'''
Created on Dec 10, 2013

@author: tsnguyen
Inspection Settings Class
'''


from translator.base.dmobject import DMObject
from translator.base.dmboolean import DMBoolean
from translator.state_type import State
from asaio.cli_interaction import CLIInteraction
class InspectionSubCommands(DMObject):
    '''
    Class for Inspect Sub Command in service policy
    '''

    
    CLASS_MAP_INSPECT_CLI = "class-map inspection_default"
    MATCH_DEFAULT_INSPECT_CLI = "match default-inspection-traffic"
    
    ifc_asa_keys = [
                # IFC key      ASA CLI                Is a default?
                ("ctiqbe",  "inspect ctiqbe",               False), 
                ("dcerpc",  "inspect dcerpc",               False), 
                ("dns",     "inspect dns",                  False),
                ("dns_preset","inspect dns preset_dns_map", True),
                ("esmtp",   "inspect esmtp",                True),
                ("ftp",     "inspect ftp",                  True),  
                ("ftp_strict","inspect ftp strict",         False),    
                ("gtp",     "inspect gtp",                  False),    
                ("h323_h225","inspect h323 h225",           True),
                ("h323_ras", "inspect h323 ras",            True),        
                ("http",    "inspect http",                 False),
                ("icmp",    "inspect icmp",                 False),
                ("icmp_error","inspect icmp error",         False),
                ("ils",     "inspect ils",                  False),
                ("ip_options","inspect ip-options",         True),
                ("ipsec_pass_thru","inspect ipsec-pass-thru",False),
                ("mgcp",    "inspect mgcp",                 False),
                ("mmp",     "inspect mmp",                  False),
                ("netbios", "inspect netbios",              True),
                ("pptp",    "inspect pptp",                 False),
                ("rsh",     "inspect rsh",                  True),
                ("rtsp",    "inspect rtsp",                 True),
                ("sip",     "inspect sip",                  True),
                ("skinny",  "inspect skinny",               True),
                ("snmp",    "inspect snmp",                 False),
                ("sqlnet",  "inspect sqlnet",               True),
                ("sunrpc",  "inspect sunrpc",               True),
                ("tftp",    "inspect tftp",                 True),
                ("waas",    "inspect waas",                 False),
                ("xdmcp",   "inspect xdmcp",                True)
                ]
    
    def __init__(self):
        '''
        Constructor
        '''
        
        DMObject.__init__(self, ifc_key = 'InspectionSettings', asa_key = 'inspect')
        self.mode_command = None
        
        for ifc, cli_prefix, is_default in InspectionSubCommands.ifc_asa_keys:
            self.register_child(DMBoolean(ifc, cli_prefix, on_value="enable"))
         
            
    
    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        ''' Translate IFC config to ASA config  '''
         
        
        if not self.has_ifc_delta_cfg():
            return
        config = self.delta_ifc_cfg_value['value']
        mode = self.mode_command if hasattr(self, 'mode_command') and self.mode_command else None
        no_len = len(no_asa_cfg_stack)
        for (ifc_type, ifc_key, inst), values in config.iteritems():
            inspect = self.get_child(ifc_key)
            inspect.mode_command = mode
            state = values.get('state', State.NOCHANGE)
            enable = values.get('value', None)
            if enable == 'disable' and state == State.MODIFY:
                values['state'] = State.DESTROY
            inspect.ifc2asa(no_asa_cfg_stack, asa_cfg_list)

        if len(no_asa_cfg_stack) > no_len:
            no_asa_cfg_stack.append(CLIInteraction(self.MATCH_DEFAULT_INSPECT_CLI))
            no_asa_cfg_stack.append(CLIInteraction(self.CLASS_MAP_INSPECT_CLI))
            
        
    