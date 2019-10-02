'''
Created on Sep 9, 2013

This module helps to structure list of ASA CLIs into hierarchy order to simplify translation
from ASA to IFC format.

After the structuring, the list of ASA CLI's will be come a list of Command, where a Command can be
a string, or a StructuredCommand.

A string corresponds to a simple CLI, such as "hostname <value>", where a StructuredCommand corresponds to
a "no" form of simple CLI, or a compound command, where beside a main commmand, there are sub-commands as well,
such as:
    object network <name>
        host <value>

The module provides two items to the applications:
1. class StructedCommand
2. function convert_to_structed_commands, which maps a list of CLI's to a list of StructedCommand's

@author: dli
Copyright (c) 2013 by Cisco Systems
'''


def convert_to_structured_commands(str_list, pos = 0, ignore_no_commands = True):
    '''Convert a list of commands, such as those in running-config, to a list of structured commands.
    @param str_list: list of strings
    @param pos: the position in str_list of the next CLI to process
    @param ignore_no_commands: boolean, indicates if to skip the "no" commands.
        The reason for having this option as default is to simplify delta generation
        function.
        The way we generate delta configuration between IFC and ASA is the following:
        - for all the configuration objects that are present in IFC dictionary, we mark their
          state as State.CREATE
        - for all those configurations that present in ASA running-configuration but not in IFC
          dictionary, we mark their state as State.DESTROY
        - for all the configuration objects that are present in IFC dictionary as well as ASA
          running-configuration, we will mark their states as State.MODIFY or State.NOCHANGE
        - for those configuration objects in ASA running-configuration in 'no' form, it means
          these objects do not prresent in the ASA running-configuration, we therefore can ignore them.
    @return list of command, where a command can be a string, or StructuredCommand

    Example:
        for str_list = ['hostanme my-asa', 'object network foo', ' host 1.2.3.4'], the result will be:
        ['hostname my-asa', StructuredCommand(command='object network foo',  sub_commands = ['host 1.2.3.4'])]
    '''
    result = []
    n = len(str_list)
    while pos < n:
        cmd, pos = convert_a_command(str_list, pos, 0, ignore_no_commands)
        if is_no_command(cmd) and ignore_no_commands:
            continue
        result.append(cmd)
    return result

def convert_a_command(str_list, pos, indent, ignore_no_commands):
    '''Convert a CLI in raw format from "running-config" to a command.
    @param str_list: list of str
        the list of raw CLI's from ASA
    @param pos: int
        the position of the next CLI in str_list to process
    @param indent: int
        the indentation level of the current command level
    @param ignore_no_commands: boolean, indicates if to skip the "no" commands
    @return tuple: (command, int)
        command: is either a str for simple CLI or StructuredCommand
                if it is 'no' command or a command with sub-commands
        int value: is the position of the next un-processed item in str_list
    '''
    line = str_list[pos]
    assert(isinstance(line, str))
    if line.startswith('no '):
        cmd = StructuredCommand(command = line[3:].strip(), is_no = True)
        pos += 1
    else:
        sub_commands, pos = get_sub_commands(str_list, pos+1, indent+1, ignore_no_commands)
        if sub_commands:
            cmd = StructuredCommand(command = line.strip(), sub_commands = sub_commands)
        else:
            cmd = line.strip()
    return cmd, pos

def get_sub_commands(str_list, pos, indent, ignore_no_commands):
    '''Create a list of sub commands from the given position in the input CLI list.
    @param str_list: list of str
        the raw output of "show running-config"
    @param pos: int
        the start position to look for sub-commands
    @param indent: str
        the indentation level to identify sub-commands
    @param ignore_no_commands: boolean, indicates if to skip the "no" commands
    @return tuple: (list of commands, int)
        the first value of the tuple is a list of commands,
        the second value of the tuple is position of the next un-processed line in the str_list
    '''
    n = len(str_list)
    result = []
    while pos < n:
        line = str_list[pos]
        assert(isinstance(line, str))
        if not line.startswith(' '*indent):
            break
        cmd, pos = convert_a_command(str_list, pos, indent, ignore_no_commands)
        if is_no_command(cmd) and ignore_no_commands:
            continue
        result.append(cmd)

    return result, pos

def is_no_command(command):
    '''Determine if a ASA command is of 'no' form command
    @param command: str or StrucutedCommand
    @return boolean: True if command is 'no' form command, or False
    '''
    if isinstance(command, str):
        return command.startswith('no ')
    return command.is_no


class StructuredCommand(object):
    '''StructuredCommand is to capture the following two aspects of an CLI:
        1. "no" form of the command
        2. sub commands
    '''
    def __init__(self, command, is_no = False, sub_commands = None):
        '''
        @param command: str
            the main command
        @param is_no: boolean
            indicate if this is a 'no' form command
        @param sub_commands: list
            list of sub-commands
        '''
        self.command = command
        self.is_no = is_no
        self.sub_commands = sub_commands

    def __eq__(self, other):
        if not isinstance(other, StructuredCommand):
            return False
        return (self.command == other.command and
                self.is_no == other.is_no and
                self.sub_commands == other.sub_commands)

    def __str__(self):
        if self.is_no:
            return 'no ' + self.command
        elif self.sub_commands:
            result = [self.command]
            for c in self.sub_commands:
                sub_result = str(c).split('\n')
                result.extend([' ' + s for s in sub_result])
            return '\n'.join(result)
        else:
            return self.command


if __name__ == "__main__":
    assert ['hostname my-asa'] == convert_to_structured_commands(['hostname my-asa'])
    assert [StructuredCommand('hostname my-asa', is_no = True)] == convert_to_structured_commands(['no hostname my-asa'], ignore_no_commands = False)
    assert [] == convert_to_structured_commands(['no hostname my-asa'])
    assert [StructuredCommand('object network foo', sub_commands = ['host 1.2.3.4'])] == convert_to_structured_commands(['object network foo', ' host 1.2.3.4'])

    raw = ['no hostname my-asa', 'object network foo', ' host 1.2.3.4']
    expected = [StructuredCommand('object network foo', sub_commands = ['host 1.2.3.4'])]
    cooked = convert_to_structured_commands(raw)
    assert expected == cooked
