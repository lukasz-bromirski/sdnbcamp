'''
Created on Jul 1, 2013

@author: dli

Copyright (c) 2013 by Cisco Systems
'''

from base.dmobject import DMObject
from base.simpletype import SimpleType
from validators import TimeValidator

class Timeouts(DMObject):
    '''
    This is for various timeout configurations.
    Global Timeout section correspond to ASDM's Firewall>Advanced>Global Timeout screen.
    It is for all the "timeout " commands.
    '''


    def __init__(self):
        '''
        Constructor
        '''
        DMObject.__init__(self, ifc_key = Timeouts.__name__, asa_key = 'timeout')

        ifc_asa_keys = [# IFC Key                    ASA Key                           Default      min      max        allow0
                        ("Connection",              "timeout conn",                   '1:0:0',    '0:5:0',  '1193:0:0',  True),
                        ("HalfClosedConnection",    "timeout half-closed",            '0:10:0',   '0:0:30', '1193:0:0',  True),
                        ("Udp",                     "timeout udp",                    '0:2:0',    '0:1:0',  '1193:0:0',  True),
                        ("Icmp",                    "timeout icmp",                   '0:0:2',    '0:0:2',  '1193:0:0',  False),
                        ("H323",                    "timeout h323",                   '0:5:0',    '0:0:0',  '1193:0:0',  False),
                        ("H225",                    "timeout h225",                   '1:0:0',    '0:0:0',  '1193:0:0',  False),
                        #Trailing space in the ASA key for Mgcp is to avoid collision with mgcp-pat
                        ("Mgcp",                    "timeout mgcp ",                  '0:5:0',    '0:0:0',  '1193:0:0',  True),
                        ("MgcpPat",                 "timeout mgcp-pat",               '0:5:0',    '0:0:0',  '1193:0:0',  True),
                        ("TcpProxyReassembly",      "timeout tcp-proxy-reassembly",   '0:1:0',    '0:0:10', '1193:0:0',  False),
                        ("FloatingConn",            "timeout floating-conn",          '0:0:0',    '0:0:30', '1193:0:0',  True),
                        ("SunRpc",                  "timeout sunrpc",                 '0:10:0',   '0:1:0',  '1193:0:0',  True),
                        #Trailing space in the ASA key for Sip is to avoid collision with other sip-* command
                        ("Sip",                     "timeout sip ",                   '0:30:0',   '0:5:0',  '1193:0:0',  True),
                        ("SipMedia",                "timeout sip_media",              '0:2:0',    '0:1:0',  '1193:0:0',  True),
                        ("SipProvisionalMedia",     "timeout sip-provisional-media",  '0:2:0',    '0:1:0',  '1193:0:0',  False),
                        ("SipInvite",               "timeout sip-invite",             '0:1:0',    '0:0:30', '1193:0:0',  False),
                        ("SipDisconnect",           "timeout sip-disconnect",         '0:2:0',    '0:0:1',  '1193:0:0',  False),
                        ("Xlate",                   "timeout xlate",                  '3:0:0',    '0:1:0',  '1193:0:0',  False),
                        ("PatXlate",                "timeout pat-xlate",              '0:0:30',   '0:0:30', '0:5:0',     False)
        ]

        for (ifc, asa, dflt, min, max, allow0) in ifc_asa_keys:
            self.register_child(Timeout(ifc, asa, dflt, min, max, allow0))

        self.register_child(AuthenticationTimeout("AuthenAbsolute",   "absolute"))
        self.register_child(AuthenticationTimeout("AuthenInactivity", "inactivity"))

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        'Override default implementation to deal with "no timeout ...", which is not accepted by ASA. Use "clear config timeout" instead'
        tmp_no_asa_cfg_stack = []
        result = DMObject.ifc2asa(self, tmp_no_asa_cfg_stack, asa_cfg_list)
        if tmp_no_asa_cfg_stack:
            'consolidate "no timeout ..." commands into "clear config timeout"'
            self.generate_cli(no_asa_cfg_stack, "clear config timeout")
        return result

    def get_translator(self, cli):
        'Override the default implementation to catch "timeout" cli without directly going through the children'
        if self.is_my_cli(cli):
            return self

    def get_child_translator(self, cli):
        for child in self.children.values():
            result = child.get_translator(cli)
            if result:
                return result
        return None

    def diff_ifc_asa(self, cli):
        '''Override the default implementation in order to simplify the code by turning CLI of the form:
               timeout conn 1:00:00 half-closed 0:10:00 udp 0:02:00 icmp 0:00:02
           into
               timeout conn 1:00:00
               timeout half-closed 0:10:00
               timeout udp 0:02:00
               timeout icmp 0:00:02
        '''
        assert cli.strip().startswith(self.asa_key)

        clis = self.normalize_cli(cli)
        if not clis:
            return
        for cmd in clis:
            translator = self.get_child_translator(cmd)
            if translator:
                translator.diff_ifc_asa(cmd)

    def normalize_cli(self, cli):
        '''Override the default implementation in order to simplify the code by turning CLI of the form:
               timeout conn 1:00:00 half-closed 0:10:00 udp 0:02:00 icmp 0:00:02
           into
               timeout conn 1:00:00
               timeout half-closed 0:10:00
               timeout udp 0:02:00
               timeout icmp 0:00:02
            @param cli: str
                string of the compact form: e.g.
                   timeout conn 1:00:00 half-closed 0:10:00 udp 0:02:00 icmp 0:00:02
            @return list of strings in normal forms, such as:
                   timeout conn 1:00:00
                   timeout half-closed 0:10:00
                   timeout udp 0:02:00
                   timeout icmp 0:00:02
        '''
        tokens = cli.split()[1:]
        pos = 0
        result = []
        while True:
            if tokens[pos] == 'uauth':#'uauth' command has three tokens
                sub_cmd = ' '.join([self.asa_key, tokens[pos], tokens[pos+1], tokens[pos+2]])
                pos += 3
            else:#others have two tokens respectively
                sub_cmd = ' '.join([self.asa_key, tokens[pos], tokens[pos+1]])
                pos += 2
            result.append(sub_cmd)
            if pos >= len(tokens):
                break;
        return result

class Timeout(SimpleType, TimeValidator):
    'Base class for all the timeout stuff'
    def __init__(self, ifc_key, asa_key, default, min, max, allow0=False):
        SimpleType.__init__(self, ifc_key=ifc_key, asa_key=asa_key, defaults=default)
        TimeValidator.__init__(self, min=min, max=max, allow0=allow0)

    def is_the_same_cli(self, cli):
        'Override the default to make sure 0:0:0 is seen the same as 0:00:00'
        this_value = map(int, self.get_value().split(':'))
        that_value = map(int, cli.split()[2].split(':'))
        return this_value == that_value

class AuthenticationTimeout(Timeout):
    def __init__(self, ifc_key, asa_cli_suffix):
        '''
        Constructor
        '''
        Timeout.__init__(self, ifc_key, "timeout uauth",
                         default = ' 0:5:0', min ='0:0:0', max = '1193:0:0')
        self.asa_gen_template = "timeout uauth %s " + asa_cli_suffix
        self.asa_suffix = asa_cli_suffix

    def get_translator(self, cli):
        'Override the default implementation as the suffix is part of the key'
        result =  SimpleType.get_translator(self, cli)
        if result:
            tokens = cli.split()
            suffix = tokens[len(tokens) - 1]
            result =  self if suffix == self.asa_suffix else None
        return result