'''
Created on Jul 25, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Classes used for CLI generation and parsing
'''

class CLIInteraction:
    '''
    Information about a CLI used for generation and parsing

    Examples:
    CLIInteraction('hostname ciscoasa')
    CLIInteraction(command='no name 171.69.1.129 dirt',
                   response_parser=cli_interaction.ignore_response_parser)
    CLIInteraction(command='nameif outside',
                   mode_command='interface GigabitEthernet0/0')
    CLIInteraction(command='no active',
                   mode_command=('call-home', 'profile CiscoTAC-1'))

    '''

    def __init__(self, command, model_key=None, mode_command=None,
                 response_parser=None, mode_response_parser=None):
        '''
        The command parameter is a string containing the CLI.

        The optional model_key parameter is the key from the device model for
            the object that generated this CLI.  It will be used to report
            errors for this CLI that can be associated with the object that
            caused the errors.

        The optional mode_command parameter is a string or a tuple of strings
            containing the mode command(s).  The command will be executed as a
            sub-command of the mode_command.

        The optional response_parser parameter is a function that will be called
            to parse the response to the command.  If the response should be
            ignored, then None should be returned.

        The optional mode_response_parser parameter is a function that will be
            called to parse the response to the mode_command.  If the response
            should be ignored, then None should be returned.

        '''
        self.command = command
        self.model_key = model_key
        self.mode_command = mode_command
        self.mode_response_parser = mode_response_parser
        self.response_parser = response_parser

    def parse_response(self, response):
        'Parses the response to this CLI command'

        if not self.response_parser:
            return response
        return self.response_parser(response)

    def __str__(self):
        return self.command

class CLIResult:
    'Result from a CLI that has been sent to the ASA'

    ERROR = 1
    INFO = 2
    WARNING = 3

    def __init__(self, cli, err_type, err_msg, model_key):
        self.cli = cli
        self.err_type = err_type
        self.err_msg = err_msg
        self.model_key = model_key

def format_cli(cli_holder):
    '''
    Formats the mode commands of indiviudal CLIs
    
    The cli_holder parameter is a list of CLIInteraction objects that
        contain the commands to send.  Mode changes will be inserted into this
        list. 

    '''

    last_mode_commands = ()
    i = 0
    while (i < len(cli_holder)):
        ci = cli_holder[i]
        optimal_mode_commands, last_mode_commands = optimize_mode_command(
            ci.mode_command, last_mode_commands)
        for mode_command in optimal_mode_commands:
            cli_holder.insert(
                i,
                CLIInteraction(
                    command=mode_command,
                    response_parser=ci.mode_response_parser
                    )
                )
            i += 1
        i += 1

def ignore_info_response_parser(response):
    'Ignores INFO response, otherwise returns original'
    return None if not response or 'INFO' in response.upper() else response

def ignore_response_parser(response):
    'Ignores any response'
    return None

def ignore_warning_response_parser(response):
    'Ignores WARNING response, otherwise returns original'
    return None if not response or 'WARNING' in response.upper() else response

def optimize_mode_command(curr_mode_commands, last_mode_commands):
    '''
    Optimizes the mode commands based on the last mode commands

    This avoids redundant commands being sent to the device.
    
    The inputs are the current mode commands and the last mode commands.  The
    output is the optimal mode commands and the full mode commands.
    
    An un-optimized example:
        policy-map NAME
         class C1
          inspect ftp
        policy-map NAME
         class C2
          inspect mgcp
    
    An optimized version of the above:
        policy-map NAME
         class C1
          inspect ftp
         class C2
          inspect mgcp

    '''

    if not curr_mode_commands:
        return (), ()

    if isinstance(curr_mode_commands, basestring):
        '''basestring takes care of both ASCII and Unicode.
        IFC sometimes sends us Unicode in the configuration parameter.
        '''
        curr_mode_commands = (curr_mode_commands,)
    if last_mode_commands:
        if curr_mode_commands == last_mode_commands:
            return (), curr_mode_commands
        else:
            for i, (curr, last) in enumerate(zip(curr_mode_commands,
                                                 last_mode_commands)):
                # Look for the longest match between the current and last mode
                # commands.  The optimal mode commands are the ones that don't
                # match.
                if curr != last:
                    break
            return curr_mode_commands[i:], curr_mode_commands
    return curr_mode_commands, curr_mode_commands
