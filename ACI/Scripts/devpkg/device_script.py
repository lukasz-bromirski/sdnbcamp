'''

ASA Device Script
Copyright (c) 2013 by Cisco Systems, Inc.

All APIs use 'device' param to identify a device to communicate. The Device is a dictionary with following information

device =  {
   'host':   <device ip address>,
   'port': <destion L4 port for communicating with the device>,
   'creds': {'username': useranme, 'password': password}
}


API returns Faults dictionary of the form:
{'status', True, 'health': [], 'faults': [fault]}
where fault is a tuple of (path, code, error_msg),
   path: a list of configuration entry keys leading to the offending configuration object
   error_msg: a str


@see devicemodel for the formation configuration parameter passed to the API's.


Created on Jun 28, 2013

@author: feliu
'''

import copy
import json
import re
import traceback
from urllib2 import HTTPError
from asaio.cli_interaction import CLIInteraction, CLIResult
from asaio.dispatch import HttpDispatch
from utils.util import pretty_dict, deliver_clis, read_clis, read_asa_version
from utils.util import deliver_sts_table, query_sts_audit_table
from utils.util import get_config_root_key, get_config_firewall_keys
from utils.util import get_all_connectors, massage_param_dict
from utils.util import hide_passwords
from utils.errors import ConnectionError, IFCConfigError, ASACommandError
import utils.env as env
from translator.cluster import ClusterConfig
from translator.devicemodel import ifc2asa, generate_asa_delta_cfg, DeviceModel
from translator.state_type import Type
from translator.sts import STS

class Status(object):
    'Possible value for "state" in the return value'
    SUCCESS =   0 # thing is fine and dandy
    TRANSIENT = 1 # Temporary failure. Script Engine will retry the configuration by calling device script API again
    PERMANENT = 2 # Configuration failure - could be due to invalid configuration parameter or feature unsupported on device etc.  Script will not retry
    AUDIT =     3 # Script can request to trigger an Audit

def get_config_dict(argv):
    '''Return the last dict object in a list of parameters, which is the configuration parameter
    '''
    dicts = filter(lambda x: isinstance(x, dict), argv)
    if len(dicts) > 0:
        return dicts[-1]
    else:
        return None

def dump_config_arg(f):
    ''' Decorator used to dump out device and configuration argument passed to an API
    '''

    def trace(*argv):
        env.debug("***** API Called: %s" % f.__name__)
        device = argv[0]

        env.debug("[Device argument]\n%s" %
                  json.dumps(hide_passwords(copy.deepcopy(device)),
                             indent=3))
        config  = get_config_dict(argv[1:])
        if config:
            env.debug("[Configuration argument]\n%s" % pretty_dict(config))

        return f(*argv)
    return trace

def exception_handler(f):
    ''' Decorator used to handle exceptions, only used for xxxModify and xxxAudit APIs for now
    '''
    def handler(*argv, **kwargs):
        config  = get_config_dict(argv[1:])
        root = get_config_root_key(config)
        result = {'state': Status.SUCCESS, 'faults': []}
        try:
            f(*argv, **kwargs)
        except ConnectionError as e:
            result['faults'] = [(root, 0, e.message)]
            result['state'] = Status.AUDIT
        except IFCConfigError as e:
            result['faults'] = e.fault_list
            result['state'] = Status.PERMANENT
        except ASACommandError as e:
            result['faults'] = e.fault_list
            result['state'] = Status.PERMANENT
        except Exception as e:
            result['faults'] = [(root, 0, "Unexpected exception: " + e.message +
                                '\n' + traceback.format_exc())]
            result['state'] = Status.PERMANENT
        finally:
            return result
    return handler

@dump_config_arg
def deviceValidate(device,
                   version):
    '''This function validates if the device matches one of the versions
    supported by the device package. This function should do a compare (regular
    expression match) the version fetched from the device with version
    string passed in the param.

    @param device: dict
        a device dictionary
    @param version: str
         a regular expression for the supported versions of the device.
         e.g: '1.0'
     @return: dict
        {'state': <state>, 'version': <version>}
    '''
    env.debug("[Version argument]\n%s" % version)

    result = {}
    asa_version, error = read_asa_version(device)
    if asa_version:
        result['version'] = asa_version
        match =  re.compile(version).match(asa_version)
        result['state'] = Status.SUCCESS if match else Status.PERMANENT
        if not match:
            result['faults'] = [(get_config_root_key({}), 0, 'Device running un-supported ASA version %s' % asa_version)]
    else: #not able to connect
        result['state'] = Status.TRANSIENT
        result['faults'] = [(get_config_root_key({}), 0, error)]
    return result


@dump_config_arg
def deviceModify(device,
                 interfaces,
                 configuration):
    ''' Update global device configuration
    @param device: dict
        a device dictionary
        @warning:  'creds' attribute should be (name, password) pair?!
    @param interfaces: list of strings
        a list of interfaces for this device.
        e.g. [ 'E0/0', 'E0/1', 'E1/0', 'E1/0' ]
    @param configuration: dict
        Device configuration configured by the user. This is configuration that does not
        depend on a graph/function. Example:
         syslog server IP
         HA peer IP
         HA mode
         Port-Channel
    @return: Faults dictionary
    '''
    env.debug("[Interfaces argument]\n%s" % pretty_dict(interfaces))

    return modify_operation(device, interfaces, configuration)

@dump_config_arg
def deviceHealth(device,
                interfaces,
                configuration):
    ''' This function polls the device. API should return a weighted device health score
    in range (0-100)

    @param device:  dict
        a device dictionary
    @return: int
        a weighted device health score in range (0-100)
    Example:
        Poll CPU usage, free memory, disk usage etc.
    '''
    env.debug("[Interfaces argument]\n%s" % pretty_dict(interfaces))

    # Note that there is no root for device configuration, so the returned path
    # is always an empty list.

    result = {}
    version, error = read_asa_version(device)
    if not version: #fail to connect
        result['faults'] = [([], 0, error)]
        result['health'] = [([], 0)]
        result['state'] = Status.TRANSIENT #same as that from xxxxAudit and xxxxModify
    else:
        result['state'] = Status.SUCCESS
        # check for cluster to see if it is ready
        cluster_health = ClusterConfig.get_health(device, configuration)
        if cluster_health:
            result['health'] = [cluster_health]
        else:
            result['health'] = [([], 100)]
    return result

@dump_config_arg
def deviceCounters(device,
                   interfaces,
                   configuration):
    '''
    This function is called periodically to report statistics associated with
    the physical interfaces of the device.

    @param device:
        a device dictionary
    @param interfaces:
        A list of the physical interfaces
        The format is:
            {
                (cifType, '', <interface name>) : {
                    'state': <state>,
                    'label': <label>
                },
                ...
            }
    @param configuration: dict
        It contains device configuration. The configuration dictionary follows
        the format described above.
    @return: dict
            The format of the dictionary is as follows
            {
              'state': <state>
              'counters': [(path, counters), ...]
            }

            path: Identifies the object to which the counter is associated.

            counters: {
              'rxpackets': <rxpackets>,
              'rxerrors': <rxerrors>,
              'rxdrops': <rxdrops>,
              'txpackets': <txpackets>,
              'txerrors': <txerrors>,
              'txdrops': <txdrops>
            }
    '''
    env.debug("[Interfaces argument]\n%s" % pretty_dict(interfaces))

    result = {'counters': []}
    if interfaces:
        cli_holder = []
        for interface in interfaces:
            cli_holder.append(CLIInteraction('show interface ' +
                                             interface[2].replace('_', '/')))
        dispatcher = HttpDispatch(device)
        try:
            messenger = dispatcher.make_command_messenger(cli_holder)
            cli_results = messenger.get_results()
        except HTTPError as e:
            env.debug('deviceCounters: %s' % e)
            result['state'] = Status.TRANSIENT
            return result

        result['state'] = Status.SUCCESS
        for interface, cli_result in zip(interfaces, cli_results):
            if cli_result and cli_result.err_type == CLIResult.INFO:
                path = [(Type.CIF, '', interface[2])]
                counters = parse_interface_counters(cli_result.err_msg)
                result['counters'].append((path, counters))
    else:
        # Check if there is connectivity to the device
        version = read_asa_version(device)[0]
        result['state'] = Status.SUCCESS if version else Status.TRANSIENT

    return result

@dump_config_arg
def deviceAudit(device,
                interfaces,
                configuration):
    ''' deviceAudit is called to synchronize configuration between IFC and the device.
    IFC invokes this call when device recovers from hard fault like reboot,
    mgmt connectivity loss etc.

    This call can be made as a result of IFC cluster failover event.

    Device script is expected to fetch the device configuration and reconcile with the
    configuration passed by IFC.

    In this call IFC will pass entire device configuration across all graphs. The device
    should insert/modify any missing configuration on the device. It should remove any extra
    configuration found on the device.

    @param device: dict
        a device dictionary
    @param interfaces: list of strings
        a list of interfaces for this device.
        e.g. [ 'E0/0', 'E0/1', 'E1/0', 'E1/0' ]
    @param configuration: dict
        Entire configuration on the device.
    @return: Faults dictionary

    '''
    env.debug("[Interfaces argument]\n%s" % pretty_dict(interfaces))

    return audit_operation(device, interfaces, configuration)

#
# FunctionGroup API
#
@dump_config_arg
def serviceAudit(device,
                 configuration):
    ''' serviceAudit is called to synchronize configuration between IFC and the device.
    IFC invokes this call when device recovers from hard fault like reboot,
    mgmt connectivity loss etc.

    This call can be made as a result of IFC cluster failover event.

    Device script is expected to fetch the device configuration and reconcile with the
    configuration passed by IFC.

    In this call IFC will pass entire device configuration across all graphs. The device
    should insert/modify any missing configuration on the device. It should remove any extra
    configuration found on the device.

    @param device: dict
        a device dictionary
    @param interfaces: list of strings
        a list of interfaces for this device.
        e.g. [ 'E0/0', 'E0/1', 'E1/0', 'E1/0' ]
    @param configuration: dict
        Entire configuration on the device.
    @return: Faults dictionary

    '''
    return audit_operation(device, [], configuration, include_shared_config=True)

@dump_config_arg
def serviceModify(device,
                  configuration):
    '''This function is called when graph is rendered as a result of a EPG attach or when any param
    within the graph is modified.

    The configuration dictionary follows the format described above.

    This function is called for create, modify and destroy of graph and its associated functions

    @param device: dict
        a device dictionary
    @param configuration: dict
        configuration in delta form
    @return: Faults dictionary
    '''
    return modify_operation(device, [], configuration)

#
# EndPoint/Network API
#
@dump_config_arg
def attachEndpoint(device,
                   configuration,
                   connector,
                   endpoint):
    '''This function is called on an EP attach. IFC identifies the EPG for the EP.
    It walks all the graphs attached to the EPG.
    For each graph it traverses each function group. For each function group it
    calls attachEndpoint for associated device.
    The device will get attachEndpoint call in context of each graph.

    @param device: dict
        a device dictionary
    @param configuration: dict
        The configuration dictionary follows the format described above.
        The configuration contains device configuration, group configuration
        for a particular graph instance and all function configuration relevant
        to the device for this graph.
    @param connector: str
        name of an end point group
    @param endpoint: str
        the ip address of the endpoint
    @return: dict
        {'state': Status.SUCCESS, 'faults': []}
    '''
    return {'state': Status.SUCCESS, 'faults': []}


@dump_config_arg
def detachEndpoint(device,
                   configuration,
                   connector,
                   endpoint):
    '''This function is called on an EP detach. IFC identifies the EPG for the EP.
    It walks all the graphs attached to the EPG.
    For each graph it traverses each function group. For each function group
    it calls detachEndpoint for associated device.
    The device will get detachEndpoint call in context of each graph.

    @param device: dict
        a device dictionary
    @param configuration: dict
        The configuration dictionary follows the format described above.
        The configuration contains device configuration,  group configuration
        for a particular graph instance and all function configuration relevant
        to the device for this graph.
    @param connector: str
        name of an end point group (EGP)
    @param endpoint: str
        the ip address of the endpoint
    @return: dict
        {'state': Status.SUCCESS, 'faults': []}
    '''
    return {'state': Status.SUCCESS, 'faults': []}

@dump_config_arg
def epHealth(device,
             name,
             configuration,
             connector,
             endpoint):
    '''This function is defined by the device if it is capable of reporting per Endpoint health.
    IFC periodically polls for endPoint health. The script can return back a health score in
    the range of (0-100) with 100 for good health.

    This function is called in context of each graph that's rendered on the device.

    @param device: dict
        a device identification dictionary
    @param name: str
        Device name
    @param configuration: dict
        It contains group configuration for a particular graph instance and function configuration
    @param connector: str
        Name of a connector within the Function on which EP is attached.
        Script can lookup the connector information passed in the configuration to
        get any connector specific information.
    @param endpoint: str
        IP address of the Endpoint. It is a string with following format:
        "x.x.x.x/32" or "x:x:x:x:x:x:x:x/128"
    @returnL: int
        Health - Integer value in range of (0-100) indicating health of the device
    '''
    pass

@dump_config_arg
def attachNetwork(device,
                  configuration,
                  connector,
                  network):
    ''' Called when a new subnet is defined for an EPG associated with this Graph
    @param device:
        a device dictionary
    @param configuration: dict
        configuration in delta form
    @param connector: str
        name of an end point group
    @param network: tuple
        (ip_address, network_mask) pair
    @return: dict
        {'state': Status.SUCCESS, 'faults': []}
    '''
    return {'state': Status.SUCCESS, 'faults': []}

@dump_config_arg
def detachNetwork(device,
                  configuration,
                  connector,
                  network):
    '''This function is called on a Network detach. IFC identifies the EPG on which
    network attach event occred. It walks all the graphs attached to the EPG.
    For each graph it traverses each function group. For each function group
    it calls detachNetwork for the associated device.
    The device will get detachNetwork call in context of each graph.

    @param device:
        a device dictionary
    @param configuration: dict
        The configuration dictionary follows the format described above.
        The configuration contains device configuration, group configuration
        for a particular graph instance and all function configuration
        relevant to the device for that graph.
    @param connector: str
        Name of an end point group.
        Script can lookup the connector information passed in the configuration
        to get any connector specific information
    @param network: tuple
        (ip_address, network_mask) pair
    @return: dict
        {'state': Status.SUCCESS, 'faults': []}
    '''
    return {'state': Status.SUCCESS, 'faults': []}

@dump_config_arg
def serviceHealth(device,
                  configuration):
    '''This function is called periodically to report health of the service function
    on the device.

    @param device:
        a device dictionary
    @param configuration: dict
        It contains device configuration, group configuration for a particular
        graph instance and function configuration. The configuration dictionary follows
        the format described above.
    @return: dict
        It is dictionary of function health represented as an integer within (0-100) range.
        Format of the dictionary is as follows

          { (path): health,  ...}

          path: Is a list identifying a function within the graph. Example
          [ vdev, vgrp, vfunc ]

          vdev - Device Name. Passed in the configuration dictionary
          vgrp - Function Group name passed in the configuration dictionary
          vfunc - function name passed in configuration dictionary

        The health dictionary will contain an entry for each function rendered on the
        device for the given graph
    '''
    result = {}
    version, error = read_asa_version(device)
    if not version: #fail to connect
        result['faults'] = [(get_config_root_key(configuration), 0, error)]
        result['state'] = Status.TRANSIENT #same as that from xxxxAudit and xxxxModify
    else:
        result['health'] = []
        result['state'] = Status.SUCCESS
        for f in get_config_firewall_keys(configuration):
            result['health'].append((f, 100))
    return result

@dump_config_arg
def serviceCounters(device,
                    configuration):
    '''
    This function is called periodically to report statistics associated with
    the service functions rendered on the device.

    @param device:
        a device dictionary
    @param configuration: dict
        It contains device configuration, group configuration for a particular
        graph instance and function configuration. The configuration dictionary follows
        the format described above.
    @return: dict
            The format of the dictionary is as follows
            {
              'state': <state>
              'counters': [(path, counters), ...]
            }

            path: Identifies the object to which the counter is associated.
              The path is a list identifying a specific instance of a connector.
              It includes device name, group name, etc. as shown below:

              path = [ vdev, vgrp, vfunc, conn ]

              vdev - Device Name. Passed in the configuration dictionary
              vgrp - Function Group name passed in the configuration dictionary
              vfunc - function name passed in configuration dictionary
              conn - connector name within the function

            counters: {
              'rxpackets': <rxpackets>,
              'rxerrors': <rxerrors>,
              'rxdrops': <rxdrops>,
              'txpackets': <txpackets>,
              'txerrors': <txerrors>,
              'txdrops': <txdrops>
            }
    '''
    result = {'counters': []}

    asa = DeviceModel()
    ifc_cfg = massage_param_dict(asa, configuration)
    asa.populate_model(ifc_cfg.keys()[0], ifc_cfg.values()[0])

    connectors = get_all_connectors(asa)
    if connectors:
        cli_holder = []
        for connector in connectors:
            cli_holder.append(CLIInteraction('show interface '
                                             + connector.get_nameif()))
        dispatcher = HttpDispatch(device)
        try:
            messenger = dispatcher.make_command_messenger(cli_holder)
            cli_results = messenger.get_results()
        except HTTPError as e:
            env.debug('serviceCounters: %s' % e)
            result['state'] = Status.TRANSIENT
            return result

        result['state'] = Status.SUCCESS
        for connector, cli_result in zip(connectors, cli_results):
            path = connector.get_config_path()
            counters = parse_connector_counters(cli_result.err_msg)
            result['counters'].append((path, counters))
    else:
        # Check if there is connectivity to the device
        version = read_asa_version(device)[0]
        result['state'] = Status.SUCCESS if version else Status.TRANSIENT

    return result

@dump_config_arg
def clusterAudit(device, interfaces,
                 configuration):
    ''' deviceAudit is called to synchronize configuration between IFC and the device.
    IFC invokes this call when device recovers from hard fault like reboot,
    mgmt connectivity loss etc.

    This call can be made as a result of IFC cluster failover event.

    Device script is expected to fetch the device configuration and reconcile with the
    configuration passed by IFC.

    In this call IFC will pass entire device configuration across all graphs. The device
    should insert/modify any missing configuration on the device. It should remove any extra
    configuration found on the device.

    @param device: dict
        a device dictionary
    @param configuration: dict
        Entire configuration on the device.
    @return: boolean
        Success/Failure

    '''
    return audit_operation(device, [], configuration)

@dump_config_arg
def clusterModify(device, interfaces,
                  configuration):
    '''This function is called when graph is rendered as a result of a EPG attach or when any param
    within the graph is modified.

    The configuration dictionary follows the format described above.

    This function is called for create, modify and destroy of graph and its associated functions

    @param device: dict
        a device dictionary
    @param configuration: dict
        configuration in delta form
    @return: Faults dictionary
    '''
    return modify_operation(device, [], configuration)


@exception_handler
def modify_operation(device,
                     interfaces,
                     configuration):
    '''Modify the configuration on ASA device.
    The configuration dictionary follows the format described above.

    This function is called for create, modify and destroy of graph and its associated functions

    @param device: dict
        a device dictionary
    @param configuration: dict
        configuration in delta form
    @return: Faults dictionary through the exception_handler decorator
    '''
    sts = STS()
    clis = ifc2asa(configuration, device, interfaces, sts)
    deliver_clis(device, clis)
    is_STS = False
    if is_STS:
        if sts.sts_table:
            deliver_sts_table(device, sts, False)

@exception_handler
def audit_operation(device,
                    interfaces,
                    configuration,
                    include_shared_config = False):
    ''' Device script is expected to fetch the device configuration and reconcile with the
    configuration passed by IFC.

    In this call IFC will pass entire device configuration across all graphs. The device
    should insert/modify any missing configuration on the device. It should remove any extra
    configuration found on the device.

    @param device: dict
        a device dictionary
    @param interfaces: list of strings
        a list of interfaces for this device.
        e.g. [ 'E0/0', 'E0/1', 'E1/0', 'E1/0' ]
    @param configuration: dict
        Entire configuration on the device.
    @param include_shared_config: boolean
        Flag to indicate if the function configuration should be modified.
    @return: Faults dictionary through the exception_handler decorator

    '''
    sts = STS()
    input_clis = read_clis(device)
    output_clis = generate_asa_delta_cfg(configuration, input_clis, device, interfaces, sts, include_shared_config)
    deliver_clis(device, output_clis)
    is_STS = False
    if is_STS:
        query_sts_audit_table(device, sts)
        if sts.sts_table:
            deliver_sts_table(device, sts, True)

CONNECTOR_COUNTER_PATTERN = None
def parse_connector_counters(show_output):
    'Parse the traffic statistics counters in the "show interface" output'
    global CONNECTOR_COUNTER_PATTERN
    if not CONNECTOR_COUNTER_PATTERN:
        CONNECTOR_COUNTER_PATTERN = re.compile(
            '.*\sTraffic Statistics' +
            '.*\s(\d+) packets input' +
            '.*\s(\d+) packets output' +
            '.*\s(\d+) packets dropped',
            re.DOTALL)

    # The ASA doesn't have support for these counters
    result = {
        'rxerrors': 0,
        'txerrors': 0,
        'txdrops': 0
    }

    m = CONNECTOR_COUNTER_PATTERN.match(show_output)
    if m:
        result['rxpackets'] = int(m.group(1))
        result['txpackets'] = int(m.group(2))
        result['rxdrops'] = int(m.group(3))
    else:
        result['rxpackets'] = 0
        result['txpackets'] = 0
        result['rxdrops'] = 0

    return result

INTERFACE_COUNTER_PATTERN = None
def parse_interface_counters(show_output):
    'Parse the hardware counters in the "show interface" output'
    global INTERFACE_COUNTER_PATTERN
    if not INTERFACE_COUNTER_PATTERN:
        INTERFACE_COUNTER_PATTERN = re.compile(
            '.*\s(\d+) packets input' +
            '.*\s(\d+) input errors' +
            '.*\s(\d+) packets output' +
            '.*\s(\d+) output errors',
            re.DOTALL)

    # The ASA doesn't have support for these counters
    result = {
        'rxdrops': 0,
        'txdrops': 0
    }

    m = INTERFACE_COUNTER_PATTERN.match(show_output)
    if m:
        result['rxpackets'] = int(m.group(1))
        result['rxerrors'] = int(m.group(2))
        result['txpackets'] = int(m.group(3))
        result['txerrors'] = int(m.group(4))
    else:
        result['rxpackets'] = 0
        result['rxerrors'] = 0
        result['txpackets'] = 0
        result['txerrors'] = 0

    return result

if __name__ == "__main__":
    device = {
        'devs': {
            'ASA-41': {
                'host': '172.23.204.41',
                'port': 443,
                'creds': {
                    'username': 'asadp',
                    'password': 'dat@package'
                }
            }
        },
        'host': '172.23.204.41',
        'port': 443,
        'creds': {
            'username': 'asadp',
            'password': 'dat@package'
        }
    }
    from utils.util import deliver_clis
    deliver_clis.enabled = False;
    result = serviceAudit(device, {})
    pass
