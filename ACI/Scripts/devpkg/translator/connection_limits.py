#
# Copyright (c) 2013 by Cisco Systems, Inc.
#
'''
Created on Nov 14, 2013

@author: linlilia

Copyright (c) 2013 by Cisco Systems
'''

import translator
import utils.util as util
from translator.base.dmobject import DMObject
from translator.base.simpletype import SimpleType
from translator.state_type import State, Type

TIMEOUT_RESET_CLI = 'reset'
IDLE_TIME_DEFAULT = '1:0:0'
RETRY_INTERVAL_DEFAULT = '0:0:15'
MAX_RETRIES_DEFAULT = '5'

class ConnectionLimitSubCommands(DMObject):
    '''
    Model after "set connection" sub-commands under class sub-command in policy-map command
    '''
    SET_CONN_TIMEOUT_CLI = "set connection timeout"

    def __init__(self):
        '''
        Constructor
        '''
        DMObject.__init__(self, ifc_key = 'ConnectionSettings', asa_key = 'set connection')
        conn_ifc_asa_keys = [# IFC Key                    ASA Key                               Default
                        #connection limits
                        ("conn_max",                  "set connection conn-max",                 '0'),
                        ("conn_max_embryonic",        "set connection embryonic-conn-max",       '0'),
                        ("per_client_max",            "set connection per-client-max",           '0'),
                        ("per_client_max_embryonic",  "set connection per-client-embryonic-max", '0'),
                        ("random_seq_num",            "set connection random-sequence-number",   'enable')
                        ]
        conn_timeout_ifc_asa_keys = [# IFC Key                    ASA Key                               Default
                        #connection timeouts
                        ("timeout_embryonic",         "set connection timeout embryonic",         '0:0:30'),
                        ("timeout_half_closed",       "set connection timeout half-closed",       '0:10:0')

        ]

        for (ifc, asa, dflt) in conn_ifc_asa_keys:
            self.register_child(ConnObj(ifc, asa, dflt))
        for (ifc, asa, dflt) in conn_timeout_ifc_asa_keys:
            self.register_child(ConnTimeoutObj(ifc, asa, dflt))
        self.register_child(ConnTimeoutIdle())
        self.register_child(ConnTimeoutDcd())

    def get_translator(self, cli):
        'Override the default implementation to catch "set connnection" cli without directly going through the children'
        if self.is_my_cli(cli):
            return self

    def get_child_translator(self, cli):
        for child in self.children.values():
            result = child.get_translator(cli)
            if result:
                return result
        return None

    def diff_ifc_asa(self, cli):
        '''
        Override the default implementation in order to simplify the code by turning CLI of the form:
                set connection conn-max 1000 embryonic-conn-max 2000 per-client-max 3000 per-client-embryonic-max 4000 random-sequence-number disable
            into
                set connection conn-max 1000
                set connection embryonic-conn-max 2000
                set connection per-client-max 3000
                set connection per-client-embryonic-max 4000
                set connection random-sequence-number disable
            turning CLI of the form:
                set connection timeout embryonic 1:2:3 half-closed 4:5:6
            into:
                set connection timeout embryonic 1:2:3
                set connection timeout half-closed 4:5:6
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
                set connection conn-max 1000 embryonic-conn-max 2000 per-client-max 3000 per-client-embryonic-max 4000 random-sequence-number disable
            into
                set connection conn-max 1000
                set connection embryonic-conn-max 2000
                set connection per-client-max 3000
                set connection per-client-embryonic-max 4000
                set connection random-sequence-number disable
            @param cli: str
            string of the compact form: e.g.
                set connection conn-max 1000 embryonic-conn-max 2000 per-client-max 3000 per-client-embryonic-max 4000 random-sequence-number disable
            @return list of strings in normal forms, such as:
                set connection conn-max 1000
                set connection embryonic-conn-max 2000
                set connection per-client-max 3000
                set connection per-client-embryonic-max 4000
                set connection random-sequence-number disable
        '''
        conn_timeout_keywords = ['embryonic', 'idle', 'half-closed']
        cli = cli.strip()
        asa_key = self.SET_CONN_TIMEOUT_CLI if cli.startswith(self.SET_CONN_TIMEOUT_CLI) else self.asa_key
        tokens = cli.split()[3:] if cli.startswith(self.SET_CONN_TIMEOUT_CLI) else cli.split()[2:]
        pos = 0
        tokens_len = len(tokens)
        result = []
        while True:
            if tokens[pos] == 'idle' and pos <= tokens_len - 3 and tokens[pos+2] == TIMEOUT_RESET_CLI: # 'idle' command has optional 'reset'
                sub_cmd = ' '.join([asa_key, tokens[pos], tokens[pos+1], tokens[pos+2]])
                pos += 3
            elif tokens[pos] == 'dcd': # 'dcd' command has optional hh:mm:ss and max_retries options
                sub_cmd = ' '.join([asa_key, tokens[pos]])
                while True:
                    pos +=1
                    if pos >= tokens_len:
                        break;
                    elif tokens[pos] not in conn_timeout_keywords:
                        sub_cmd = ' '.join([sub_cmd, tokens[pos]])
            else:#others have two tokens respectively
                sub_cmd = ' '.join([asa_key, tokens[pos], tokens[pos+1]])
                pos += 2
            result.append(sub_cmd)
            if pos >= tokens_len:
                break;
        return result

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''
        Override the default implementation for translating IFC config to ASA config.
        We need to pass the mode_command to the children objects because
        all of the connection limits sub-commands are under submode of class <class-map>:
            policy-map global_policy
             class connection_limits_default
              set connection ...
        '''
        assert self.has_ifc_delta_cfg()

        action = self.delta_ifc_cfg_value['state']
        if action == State.NOCHANGE:
            return

        for child in self.children.values():
            child.mode_command = self.mode_command if hasattr(self, 'mode_command') and self.mode_command else None
            child.ifc2asa(no_asa_cfg_stack, asa_cfg_list)

class ConnObj(SimpleType):
    '''
    Model for connection limits settings sub-commands:
       set connection {[conn-max n] [embryonic-conn-max n] [per_client_max_embryonic n] [per-client-max n] [random_seq_num {enable|disable}]}
    and base model for class ConnTimeoutObj
    '''
    def __init__(self, ifc_key, asa_key, default):
        '''
        Constructor
        '''
        SimpleType.__init__(self, ifc_key, asa_key, defaults=default)

    def parse_single_parameter_cli(self, cli):
        return ' '.join(cli.split()[-1:])

class ConnTimeoutObj(ConnObj):
    '''
    Model for connection limits timeout sub-commands(base model ConnObj):
        set connection timeout {[embryonic hh:mm:ss] [half-closed hh:mm:ss]}
    '''
    def __init__(self, ifc_key, asa_key, default):
        '''
        Constructor
        '''
        ConnObj.__init__(self, ifc_key, asa_key, default)

    def is_the_same_cli(self, cli):
        '''
        Override the default implementation to make the h:m:s is seen as h:0m:0s. timeout format in hh:mm:ss
        '''
        return is_the_same_time_out_value(self.get_value(), cli.split()[4])

class ConnTimeoutIdle(SimpleType):
    '''
    Model for connection limits timeout sub-command:
        set connection timeout idle hh:mm:ss [reset]
    '''
    def __init__(self):
        '''
        Constructor
        '''
        SimpleType.__init__(self, 'timeout_idle', 'set connection timeout idle', asa_gen_template='set connection timeout idle %(idle_time)s', defaults={'idle_time': IDLE_TIME_DEFAULT})

    def get_cli(self):
        '''
        Generate the CLI for this single CLI with optional parameter 'reset'
        '''
        assert self.has_ifc_delta_cfg()
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        reset_option = (config.get('idle_reset') == 'enable')  if config is not None else False   # default value for reset: disable
        reset_option = ' ' + TIMEOUT_RESET_CLI if reset_option else ''

        return SimpleType.get_cli(self) + reset_option

    def parse_multi_parameter_cli(self, cli):
        '''
        Override the default implementation in case the CLI does not match asa_gen_template due to optional
        parameter 'reset'
        '''
        # Take care of the mandatory parameters
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

        # Take care of the optional parameters
        tokens = cli.split()
        # The number of mandatory parameters is the same as the asa_gen_template, i.e. 'service-policy global_policy global'
        if (result is None) or (len(tokens) == len(self.asa_gen_template.split())):
            return result # doesn't match or no optional parameter

        if TIMEOUT_RESET_CLI in tokens[-1:]: # e.g. set connection timeout idle 2:3:4 reset
            result[(Type.PARAM, 'idle_reset', TIMEOUT_RESET_CLI)] = {'state': State.NOCHANGE, 'value': 'enable'}
        return result

    def is_the_same_cli(self, cli):
        '''
        Override the default implementation to make the h:m:s is seen as h:0m:0s. timeout format in hh:mm:ss
        '''
        output_cli = self.parse_cli(self.get_cli().strip())
        input_cli = self.parse_cli(cli)

        if len(output_cli.values()) != len(input_cli.values()): # if one side contains the optional 'reset' and another side doesn't.
            return False

        output_timeout = output_cli.values()[-1]['value']
        input_timeout = input_cli.values()[-1]['value']

        if len(output_cli.values()) == 1:
            return is_the_same_time_out_value(output_timeout, input_timeout)
        else:
            return is_the_same_time_out_value(output_timeout, input_timeout) and output_cli.values()[-2]['value'] == input_cli.values()[-2]['value']

class ConnTimeoutDcd(SimpleType):
    '''
    Model for connection limits timeout sub-command:
        set connection timeout dcd hh:mm:ss [max_retries]
    '''
    def __init__(self):
        '''
        Constructor
        '''
        SimpleType.__init__(self, 'timeout_dcd', 'set connection timeout dcd', asa_gen_template='set connection timeout dcd %(retry_interval)s %(max_retries)s', defaults={'retry_interval': RETRY_INTERVAL_DEFAULT, 'max_retries': MAX_RETRIES_DEFAULT})

    def is_the_same_cli(self, cli):
        '''
        Override the default implementation to make the h:m:s is seen as h:0m:0s. timeout format in hh:mm:ss
        Also need to compare the optional value of max_retries
        '''
        output_cli = self.parse_cli(self.get_cli().strip())
        input_cli = self.parse_cli(cli)

        output_timeout = output_cli.values()[0]['value']
        input_timeout = input_cli.values()[0]['value']

        if len(output_cli.values()) == 1:
            return is_the_same_time_out_value(output_timeout, input_timeout)
        else:
            return is_the_same_time_out_value(output_timeout, input_timeout) and output_cli.values()[1]['value'] == input_cli.values()[1]['value']

    def parse_multi_parameter_cli(self, cli):
        '''Override the default implementation in case the CLI does not have optional max_retries value
        '''
        # Take care of the optional parameters
        tokens = cli.split()

        if len(tokens) < len(self.asa_gen_template.split()):
            cli += ' ' + MAX_RETRIES_DEFAULT

        return SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = self.asa_gen_template)

def is_the_same_time_out_value(this_time_out, that_time_out):
    '''
    Compare two timeout value to see if they are the same.  h:m:s is seen as h:0m:0s and they are treated as the same CLI value.
    Timeout format in hh:mm:ss
    '''
    if ':' not in this_time_out:
        return this_time_out.lstrip('0') == that_time_out.lstrip('0')

    this_value = map(int, this_time_out.split(':'))
    that_value = map(int, that_time_out.split(':'))
    return this_value == that_value
