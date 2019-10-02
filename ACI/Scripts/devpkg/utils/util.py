'''
Created on Jul 25, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Common utility functions
'''

from collections import OrderedDict
import json
import re
import copy
import socket
import struct

from asaio.dispatch import HttpDispatch
from asaio.cli_interaction import CLIInteraction
from translator.state_type import State, Type
from translator.structured_cli import convert_to_structured_commands
from utils.errors import ConnectionError, ASACommandError
import utils.env as env


def connection_exception_handler(f):
    ''' Decorator used to handle connection exceptions, only used for read_clis and delivelr_clis APIs for now
    '''
    def handler(*argv):
        try:
            return f(*argv)
        except IOError as e:
            raise ConnectionError(str(e))
        except:
            raise
    return handler

def key_as_string(obj):
    ''' This function makes the key into string in a dictionary.
    '''

    if isinstance(obj, dict):
        result = OrderedDict()
        for key, value in obj.iteritems():
            if isinstance(value, dict):
                result[repr(key)] = key_as_string(value)
            else:
                result[repr(key)] = value
        return result
    else:
        return obj

def pretty_dict(obj, indent=3):
    ''' This function prints a dictionary in a nicer indented form.
    '''
    try:
        return json.dumps(key_as_string(obj), indent=indent)
    except Exception:
        # If not JSON serializable
        return str(obj)

def normalize_param_dict(param_dict):
    '''
    Normalize a param dictionary by extracting the 'key' and 'value' into a new
    dictionary, recursively.

    @param param_dict: scalar value or param dictionary
        if it's a param dictionary, then each entry is of the format:
            (type, key, instance): {'state': state,
                                    'device': device,
                                    'connector': connector,
                                    'value':  scalar value or param dictionary}
    @return: scalar value or param dictionary
        if param_dict is a param dictionary, then return the a new dictionary
            with just the 'key' and 'value'.
        otherwise param_dict is returned
    '''

    if not isinstance(param_dict, dict):
        return param_dict

    result = {}
    for (kind, key, instance), cfg_value in param_dict.iteritems():
        'Will deprecate the check for target in the future, it should be handled at the program initialized'
        if 'target' in cfg_value:
            value = cfg_value['target']
        elif 'value' in cfg_value:
            value = cfg_value['value']
        if isinstance(value, dict):
            value = normalize_param_dict(value)
        result[key] = value
    return result


def normalize_state_param_dict(param_dict):
    '''
    Normalize a param dictionary by extracting the 'key' and 'value' into a new
    dictionary, recursively.

    @param param_dict: scalar value or param dictionary
        if it's a param dictionary, then each entry is of the format:
            (type, key, instance): {'state': state,
                                    'device': device,
                                    'connector': connector,
                                    'value':  scalar value or param dictionary}
    @return: scalar value or param dictionary
        if param_dict is a param dictionary, then return the a new dictionary
            with just the 'key' and 'value'.
        otherwise param_dict is returned
    '''

    if not isinstance(param_dict, dict):
        return param_dict

    result = {}
    for (kind, key, instance), cfg_value in param_dict.iteritems():
        'Will deprecate the check for target in the future, it should be handled at the program initialized'
        if 'target' in cfg_value:
            value = cfg_value['target']
        elif 'value' in cfg_value:
            value = cfg_value['value']
        if isinstance(value, dict):
            value = normalize_state_param_dict(value)
        result[key] = value
        result[key + '_state'] = cfg_value['state']
    return result

def ifcize_param_dict(param_dict):
    '''Reverse the operation of util.normalize_param_dict
    @param param_dict: dict
        A configuration diction in the normal format, e.g:
         {'Hostname': 'my-asa'}
    @return dict in the IFC format,
        For the above example, the return value is:
         {(Type.PARAM, 'Hostname', ''), {'state': State.NOCHANGE, 'value': 'my-asa'}}
    @todo: move it into util. But encountered cyclic-dependency problem.

    '''
    if not isinstance(param_dict, dict):
        return param_dict

    result = {}
    for key, value in param_dict.iteritems():
        kind = Type.FOLDER if isinstance(value, dict) else Type.PARAM
        if isinstance(value, dict):
            value = ifcize_param_dict(value)
        result[(kind, key, '')] = {'state': State.NOCHANGE, 'value': value}
    return result


def filter_out_sacred_commands(output_clis):
    '''Remove commands that may cause disruption of communication between IFC and the ASA device.
    @param output_clis: list of CLIInteraction's
    @return output_clis
    '''
    mgmt_intf = 'management'
    sacred_commands  = ['^no route ' + mgmt_intf,
                        '^no http enable',
                        '^no http .+ ' + mgmt_intf]

    for sacred in sacred_commands:
        cmds = filter(lambda text: re.compile(sacred).match(str(text).strip()), output_clis)
        for cmd in cmds:
            output_clis.remove(cmd)
    return output_clis

@connection_exception_handler
def deliver_clis(device, clis, transformers=[filter_out_sacred_commands], save_config = True):
    '''Deliver a list of CLI's to an ASA device
    @param device: dict
        a device dictionary
    @param clis: list of CLIIneraction's
    @param transformers: list of function that takes one argument and return an object
        the purpose of a transformer is to transform ASA configuration to a desired format
        before actually sending them down to the ASA device.
        The order of the application of the transformer is the reverse given in the parameter,
        i.e. if the transformers is [a, b], the result will be a(b(config)).
        a list of CLI objects.
    @param save_config: boolean
        indicate if the running-config should be saved to startup-config if the configuration
        is delivered successfully.
    @return: True if successful in delivery, or ASACommandError or ConnectionError exception will be raised.
    '''
    if not deliver_clis.enabled:
        env.debug("[CLIs would be delivered]\n%s\n" % '\n'.join([str(cli) for cli in clis]))
        return True
    if not clis:
        return True;

    if transformers:
        for transformer in reversed(transformers):
            clis = transformer(clis)
    dispatcher = HttpDispatch(device)
    def dispatch(clis):
        'deliver a list of CLIInteraction, and return list errors if any'
        messenger = dispatcher.make_command_messenger(clis)
        results = messenger.get_results()
        errs = filter(lambda x: x != None and x.err_msg != None and len(x.err_msg.strip()) > 0, results)
        return errs
    errs = dispatch(clis)
    if not errs:
        def is_cluster_config(clis):
            return any(str(cli).find('cluster group') >= 0 for cli in clis)

        if save_config and not is_cluster_config(clis):
            # 'wr mem' will fail during cluster setup so bypass now. Defer till cluster state is stable.
            write_mem = CLIInteraction("write mem",
                                       response_parser = lambda response: None if '[OK]' in response else response)
            errs = dispatch([write_mem])
            if not errs:
                return True
        else:
            return True

    faults = []
    for err in errs:
        faults.append((err.model_key, 0, err.err_msg))
    raise ASACommandError(faults)

''' One can turn deliver_clis.enabled attribute on/off during testing.
'''
deliver_clis.enabled = True

@connection_exception_handler
def read_clis(device, transformers=[convert_to_structured_commands, lambda x: x.split('\n')]):
    '''Read running-configuration from ASA device
    @param device: dict
        a device dictionary
    @param transformers: list of function that takes one argument and return an object
        the purpose of a transformer is to transform ASA configuration to a desired format.
        The order of the application of the transformer is the reverse given in the parameter,
        i.e. if the transformers is [a, b], the result will be a(b(config)).
    @return: list of CLI's
    '''
    dispatcher = HttpDispatch(device)
    messenger = dispatcher.make_read_config_messenger()
    result = messenger.read()
    if result and transformers:
        for transformer in reversed(transformers):
            result = transformer(result)
    return result

def deliver_sts_table(device, sts, is_audit):
    '''
    Send STS table to ASA device
    @param device: dict
        a device dictionary
    @param table; dict
        an STS dictionary
    @param is_audit: boolean
        True if this is an audit operation else False
    '''
    table = sts.sts_table
    if not deliver_clis.enabled:
        env.debug("[STS table would be delivered]\n\n")
        return True
    if not table:
        return True
    dispatcher = HttpDispatch(device)
    if is_audit:
        messenger = dispatcher.make_sts_audit_write_messenger(sts)
    else:
        messenger = dispatcher.make_sts_write_messenger(sts)
    results = messenger.get_results()
    if results:
        faults = []
        faults.append(('STS', 0, results))
        raise ASACommandError(faults)

def query_sts_audit_table(device, sts):
    '''
    Query STS table from ASA device
    @param device: dict
        a device dictionary
    @param table; dict
        an STS dictionary
    '''
    table = sts.sts_table
    if not device:
        error = "query_sts_table: fails to read response for quering sts table"
        env.debug(error)
        return (None, error)
    dispatcher = HttpDispatch(device)
    messenger = dispatcher.make_sts_audit_read_messenger(sts)
    results = messenger.get_results()
    if results:
        faults = []
        faults.append(('STS', 0, results))
        raise ASACommandError(faults)

def query_asa(device, query_cmd):
    '''Read information back from the given device
    @param device: dict
        a device dictionary
    @param query: str, a show command cli, like "show run access-list bla"
    @return tuple with:
        1) response string from ASA; or None if cannot connect to the device
        2) any error or exception string, otherwise None
    @attention:  PLEASE do not use this API to make configuration change on the device
    '''
    if not device:
        error = "query_asa: fails to read response for command '%s'. Error: %s" % (query_cmd, 'empty device dictionary')
        env.debug(error)
        return (None, error)
    if not query_cmd.strip().startswith('show'):
        error = "query_asa: '%s' is not a show command, discarded" % query_cmd
        env.debug(error)
        return (None, error)
    try:
        dispatcher = HttpDispatch(device)
        messenger = dispatcher.make_shows_messenger([query_cmd])
        result =  messenger.read()
        if result == 'Command failed\n':
            return None, None
        if '\nERROR: %' in result:
            return None,None
        return result, None
    except Exception as e:
        env.debug("query_asa: fails to read response for command '%s'. Error: %s" % (query_cmd, e))
        return (None, str(e))

def read_asa_version(device):
    '''Read the version information from the given device
    @param device: dict
        a device dictionary
    @return tuple with:
        1) version string, such as '9.0(3)'; or None if cannot connect to the device
        2) any error
    '''
    version_line = 'Cisco Adaptive Security Appliance Software Version'
    pattern = r'^'+ version_line + ' (\S+)'
    result, error =  query_asa(device, 'show version | grep ' + version_line)
    if not result:
        return (None, error)
    for line in result.split('\n'):
        m = re.match(pattern, line)
        if m:
            return (m.group(1), None)
    return (None, None)

def set_cfg_state(ifc_cfg_dict, state):
    '''Set the state of each entry in the a given IFC configuration
     to a given state.
    @param ifc_cfg_dict: dict
        IFC configuration dictionary
    @param state: State
    '''

    if 'state' in  ifc_cfg_dict:
        ifc_cfg_dict['state'] = state

    for value in ifc_cfg_dict.values():
        if not isinstance(value, dict):
            continue
        if not 'state' in  value:
            set_cfg_state(value, state)
            continue
        value['state'] = state

        if 'cifs' in value:
            key_of_value = 'cifs'
        elif 'target' in value:
            key_of_value = 'target'
        else:
            key_of_value = 'value'

        ifc_cfg_dict = value.get(key_of_value)
        if isinstance(ifc_cfg_dict, dict):
            set_cfg_state(ifc_cfg_dict, state)

def fill_key_strings(param_dict):
    '''The configuration parameter passed to us from IFC runtime have key value missing for certain entries.
    These entries are for the following types:
        - Type.DEV
        - Type.GRP
        - Type.CONN
        - TYPE.ENCAP
        - TYPE.ENCAPASS
        - TYPE.VIF
    However, our scripts work on key rather than type. So there is a need to fill in the key values for
    all the entries.
    @param param_dict: IFC configuration parameter
    @return param_dict
    '''

    for (kind, key, instance), cfg_value in param_dict.items():
        value = cfg_value.get('value')
        if isinstance(value, dict):
            fill_key_strings(value)
        new_key = fill_key_strings.type2key.get(kind, '')
        if new_key:
            param_dict.pop((kind, key, instance))
            '''For Connector, fill key as 'CONN' and change instance name as external_<instance> or
            internal_<instance>
            '''
            if (kind == Type.CONN) and (key != 'CONN'):
                instance = key + '_' + instance
            param_dict[(kind, new_key, instance)] = cfg_value
    return param_dict

'Type to Key mapping for fill_key_strings function'
fill_key_strings.type2key = {
            Type.DEV:      'DeviceModel',
            Type.GRP:      'SharedConfig',
            Type.CONN:     'CONN',
#             Type.RELATION: 'IntfConfigRel',
            Type.ENCAP:    'VLAN',
            Type.ENCAPASS: 'ENCAPASS',
            Type.ENCAPREL: 'ENCAPREL',
            Type.VIF:      'VIF' }


def get_config_root_key(configuration):
    'Return the key to the root entry of an IFC configuration parameter'
    return [configuration.keys()[0]] if configuration else []


def get_config_firewall_keys(configuration):
    'Return the list of keys to the Firewall entries in an IFC configuration parameter'
    result = []
    if not configuration:
        return result
    kind, root_key, instance = configuration.keys()[0]
    if kind != Type.DEV:
        return result
    hits = filter(lambda (kind, key, instance):  kind == Type.GRP, configuration.values()[0]['value'].keys())
    if not hits:
        return result
    grp_key = hits[0]
    grp_config = configuration.values()[0]['value'][grp_key]
    root_key = configuration.keys()[0]
    hits = filter(lambda (kind, key, instance):  kind == Type.FUNC, grp_config['value'].keys())
    for key in hits:
        result.append([root_key, grp_key, key])
    return result


def massage_param_dict(asa, ifc_delta_cfg_dict, transformers = None):
    '''Adjust the configuration dictionary parameter passed to us by IFC to a format suited to us.
    @param asa:  DeviceModel
    @param ifc_delta_cfg_dict: IFC configuration parameter dictionary
    @param transformers: list of function that takes one argument and return an object
        the purpose of a transformer is to transform IFC configuration dictionary to a desired format.
        The order of the application of the transformer is the reverse given in the parameter,
        i.e. if the transformers is [a, b], the result will be a(b(ifc_delta_cfg_dict)).
    @return dict
        if_cfg_dict is a equivalent of ifc_delta_cfg_dict but massaged for ifc2asa or
        generate_ifc_delta_cfg methods
    '''
    if not ifc_delta_cfg_dict:
        result = {(Type.DEV, asa.ifc_key, ''):  {'state': State.NOCHANGE, 'value': ifc_delta_cfg_dict}}
    else:
        kind, key, instance = ifc_delta_cfg_dict.keys()[0]
        if kind == Type.DEV: #for the complete configurations: device, group, function
            result = ifc_delta_cfg_dict
        else:#device configuration
            result = {(Type.DEV, asa.ifc_key, ''):  {'state': State.NOCHANGE, 'value': ifc_delta_cfg_dict}}
        'Do not modify the parameter passed to us by IFC.'
        result = copy.deepcopy(result)

    'Apply the transformations required'
    if not transformers:
        transformers = []
    transformers.append(fill_key_strings)
    for transformer in reversed(transformers):
        result = transformer(result)
    return result

def get_all_connectors(device_model):
    shared_config = device_model.get_child('SharedConfig')
    firewalls = shared_config.get_child('Firewall')

    result = []
    for firewall in firewalls.children.values():
        for connector in firewall.get_child('CONN').children.values():
            result.append(connector)
    return result

def normalize_ipv6_address(addr):
    '''
    Normalizes ipv6 address, including host address and network address.
    The following is a few example of normalized result: case converted to lower case,
    leading 0 suppressed, host part masked according to the prefix length in the case
    of network address. Example:
    'F800::1' -> 'f800::1'
    '2002:A00:55:6::0:0000:6' -> '2002:a00:55:6::6'
    '2002:A00:60:6::2/29' -> '2002:a00::/29'
    '''

    assert(addr and isinstance(addr, str) and ':' in addr)
    addr = addr.lower()
    is_network_addr = '/' in addr
    if is_network_addr:
        # e.g: '2002:a00:60:6::2/29'
        addr, prefix_len = addr.split('/')
        host_len = 128 - int(prefix_len)
        # unpack format '!QQ': '!' is network byte order, 'Q' is unsigned long long
        hi, low = struct.unpack('!QQ', socket.inet_pton(socket.AF_INET6, addr))
        hex_str = str(hex(((hi << 64 | low) >> host_len << host_len)))
        # hex_str: '0x20020a000000....0000L'
        hex_str = hex_str[2 : len(hex_str) - 1] # remove the leading '0x' and trailing 'L'
        # convert to the format that the socket API will take, e.g.: '2002:0a00:0000....0000'
        # ipv6 address is 32 hex digits, make it in full size
        hex_str = '0' * (32 - len(hex_str)) + hex_str
        addr = ':'.join([hex_str[i * 4 : (i + 1) * 4] for i in range(0, 8)])
        internal_addr = socket.inet_pton(socket.AF_INET6, addr)
        addr = socket.inet_ntop(socket.AF_INET6, internal_addr)
        return addr + '/' + prefix_len
    else: # host address
        internal_addr = socket.inet_pton(socket.AF_INET6, addr)
        return socket.inet_ntop(socket.AF_INET6, internal_addr)

def normalize_interface_name(intf):
    '''
    Normalizes interface, sub-interface, and port-channel name. For example:
        'g0/0'  -> 'GigabitEthernet0/0'
        'Gig0/1'-> 'GigabitEthernet0/1'
        'm0/0'  -> 'Management0/0'
        'Te0/8' -> 'TenGigabitEthernet0/8'
        'Eth1/1.20' -> 'Ethernet1/1.20'
        'Po9'   -> 'Port-channel9'
    '''

    if not intf:
        return
    intf = intf.strip()
    intf = pattern_replace(r'([gG][\D]*)[\d]+/[\d]+.*$', 'GigabitEthernet', intf)
    intf = pattern_replace(r'([mM][\D]*)[\d]+/[\d]+.*$', 'Management', intf)
    intf = pattern_replace(r'([tT][\D]*)[\d]+/[\d]+.*$', 'TenGigabitEthernet', intf)
    intf = pattern_replace(r'([eE][\D]*)[\d]+/[\d]+.*$', 'Ethernet', intf)
    intf = pattern_replace(r'([pP][\D]*)[\d]+.*$', 'Port-channel', intf)
    return intf

def pattern_replace(pattern, replace, source):
    '''
    Find 'pattern' in 'source' and replace the first group with 'replace'.
        'pattern' example: '([gG][\D]*)[\d]+/[\d]+.*$'
        'replace' example: 'GigabitEthernet'
        'source' example: 'g0/0'
        return result: 'GigabitEthernet0/0'
    For interface replacement, it happens if and only if the interface will be accepted
    by the device, in another word, it must be the prefix of the full interface name.
    '''
    p = re.compile(pattern)
    m = p.match(source)
    if m:
        prefix = m.group(1)
        if replace.lower().startswith(prefix.lower()):
            return re.sub(prefix, replace, source)
    return source

def hide_passwords(device):
    '''
    Hide the passwords in the device dictonary by replacing them with '<hidden>.
    This should be done on a deep copy, since the dictionary will be modified.
    '''

    if 'devs' in device:
        for value in device['devs'].itervalues():
            hide_passwords(value)
    if 'creds' in device and 'password' in device['creds']:
        device['creds']['password'] = '<hidden>'

    return device
