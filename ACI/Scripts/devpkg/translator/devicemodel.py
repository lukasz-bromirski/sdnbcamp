'''
Created on Jun 12, 2013

@author: dli
Copyright (c) 2013 by Cisco Systems

'''
from asaio.cli_interaction import format_cli
from utils.util import set_cfg_state, massage_param_dict
from utils.errors import IFCConfigError
from state_type import Type, State

from base.dmobject import DMObject
from base.dmlist import DMList

from firewall import Firewalls
from port_channel_member import PortChannelMembers
from rule.access_rule import AccessGroupGlobal, AccessListDeployment, AccessListList
from timeouts import Timeouts

from logging import LoggingConfig
from failover import FailoverConfig
from cluster import ClusterConfig

from basic_threat_detect import BasicThreatDetection
from advanced_threat_detect import AdvancedThreatDetection
from scanning_threat_detect import ScanningThreatDetection
from netflow_objects import NetFlowObjects

from connector import Vifs, Vlan, EncapAss
from vxlan_nve import VxlanPort, NVE, TVIs
from interface_config import InterfaceConfig

from network_object import HostObjects, FQDNObjects, RangeObjects, SubnetObjects
from service_object import ICMP4Objects, ICMP6Objects, ProtocolObjects, TCPObjects, UDPObjects
from network_object_group import NetworkObjectGroups
from service_object_group import ServiceObjectGroups

from ip_audit import IPAudit
from ntp import NTP
from dns import DNS
from smart_call_home import SmartCallHome

from service_policy import GlobalServicePolicyContainer

def ifc2asa(ifc_delta_cfg_dict, device = None, interfaces = None, sts = None, include_shared_config = True):
    '''Generate ASA delta configuration from configuration in IFC delta dictionary form.

    @param ifc_delta_cfg_dict: dict
    for serviceModiy, it is the form
        configuration = {
          (device) : {
              # Device Shared configuration
             (folders): {
                (folders): {
                   (params):
                    ...
                },
                (params):
                ...
             }
             (functionGroup Config): {
                 (connectors):

                 (folders): {
                    (folders): {
                       (params):
                        ...
                    },
                    (params):
                    ...
                 }

                 (function) : {
                     (folders): {
                        (folders): {
                           (params):
                            ...
                        },
                        (params):
                        ...
                     }
                 }
             }
          }

        for deviceModify, it is of the form
        configuration = {
                 (folders): {
                    (folders): {
                       (params):
                        ...
                    },
                    (params):
                    ...
             }
          }


        Configuration Dictionary Format:

            (Type, Key, Instance) : {'state': State, 'device': Device, 'connector': Connector, 'value': Value}
            #
            # Type of attribute
            #
            Type = Insieme.Fwk.Enum(
                DEV=0,
                GRP=1,
                CONN=2,
                FUNC=3,
                FOLDER=4,
                PARAM=5
            )

            #
            # State of the attribute
            #
            State = Insieme.Fwk.Enum(
                NOCHANGE=0,
                CREATE=1,
                MODIFY=2,
                DESTROY=3

            Key: the key of the configuration element given in the device specification file

            Instance: the instance identifier of a configuration object, such the name of an ACL

            Connector: the connector name

            Device: the device name, such as the case in a HA configuration situation.

    @param device: dict
        to identify the ASA device, passed in from device_script APIs
    @param interfaces: dict
        The format is similar to configuration parameter.
        Interfaces = {
            (cifType, '', <interface name>) : {
                      'state': <state>,
                      'label': <label>
            },
          ...
        }

        Example:
        {
            (11, '', 'Gig0_1'): {
                    'state': 1,
                    'label': 'external'
             },
            (11,'', 'Gig0_2'): {
                    'state': 1,
                    'label': 'internal'
            },
            (11, '', 'Gig0_3'): {
                    'state': 1,
                    'label': 'mgmt',
            },
            (11, '', 'Gig0_4'): {
                    'state': 1.
                    'label': 'cluster'
            }
        }

    @param sts: dict
        to identify the STS external and internal tag
    @param include_shared_config: boolean
        Flag to indicate if the function configuration should be modified.
    @return list of CLI's
    '''
    asa = DeviceModel(device, interfaces, include_shared_config)
    'ifc_cfg is a copy of ifc_delta_cfg_dict suited for us.'
    ifc_cfg = massage_param_dict(asa, ifc_delta_cfg_dict)

    '''Since the input dictionary is in arbitrary order, we use two-pass approach to make sure resulting
    CLI list is in the right order given in the device model.
    '''

    #1st pass
    asa.populate_model(ifc_cfg.keys()[0], ifc_cfg.values()[0])
    faults = asa.validate_configuration()
    if faults:
        raise IFCConfigError(faults)

    #2nd pass
    cli_list = []
    no_cli_stack = []
    asa.ifc2asa(no_cli_stack, cli_list)

    #gather result from positive and negative forms for the CLIs
    result = no_cli_stack
    result.reverse() #last in first out for the 'no' CLIs
    result.extend(cli_list)
    format_cli(result)

    #update sts table 
    if asa.sts_table:
        sts.sts_table = asa.sts_table
    return result

def generate_ifc_delta_cfg(ifc_cfg_dict, asa_clis, device = None, interfaces = None):
    '''Compare ifc configuration with asa configuration , and produce
    ifc configuration delta.

    @param asa_clis: list
        input/out list of CLI's read from ASA device
    @param ifc_cfg_dict: dict
        the configuration of ASA in IFC dictionary format. It will be modified
        after the comparison.
    @param device: dict
        to identify the ASA device, passed in from device_script APIs
    @param interfaces: list
        physical interfaces names passed in from device_script APIs
    @return dict
        a copy of ifc_cfg_dct but with the state of each entry set to indicate
        if a modification operation or create operation is required.
    '''
    asa = DeviceModel(device, interfaces)

    def create_missing_ifc_delta(ifc_cfg):
        'Transformer to fill in the missing folders. This is important for configuration deletion'
        asa.populate_model(ifc_cfg.keys()[0], ifc_cfg.values()[0])
        'The following call will modify ifc_cfg'
        asa.create_missing_ifc_delta_cfg()
        return ifc_cfg

    def set_cfg_state_2_CREATE(ifc_cfg):
        'Transformer to set the State of each entry to CREATE, the default state of all entries'
        set_cfg_state(ifc_cfg, State.CREATE)
        return ifc_cfg

    'ifc_cfg is a copy of ifc_cfg_dict suited for us.'
    ifc_cfg = massage_param_dict(asa, ifc_cfg_dict,
                                 transformers=[set_cfg_state_2_CREATE,
                                               create_missing_ifc_delta])

    '''Since the input dictionary is in arbitrary order, we use two-pass approach to make sure resulting
    CLI list is in the right order given in the device model.
    '''
    for cli in asa_clis:
        translator = asa.get_translator(cli)
        if translator:
            translator.diff_ifc_asa(cli)
    return ifc_cfg

def generate_asa_delta_cfg(ifc_cfg, asa_cfg, device = None, interfaces = None, sts = None, include_shared_config = True):
    '''Generate CLIs that represent the delta between given IFC configuration and ASA configuration
    @param ifc_cfg: dict
    @param asa_cfg: list of CLIs
    @param device: dict
        to identify the ASA device, passed in from device_script APIs
    @param interfaces: list
        physical interfaces names passed in from device_script APIs
    @param sts: dict
        to identify the STS external and internal tag
    @param include_shared_config: boolean
        Flag to indicate if the function configuration should be modified.
    @return: list of CLIs
    '''
    ifc_delta_cfg = generate_ifc_delta_cfg(ifc_cfg, asa_cfg, device, interfaces)
    return ifc2asa(ifc_delta_cfg, device, interfaces, sts, include_shared_config)

class InterfaceLabel(object):
    'The enumeration of the interface labels defined in device_specifciation.xml'
    External = "ext"
    Internal = "int"
    Mgmt     = "mgmt"
    Utility  = "util"
    FailoverLan  = "lan"   # The LAN based failover connection between the two failover devices
    FailoverLink = "link"  # The link(stateful) failover connection between the two failover devices
    ClusterControLink = "ccl"

class DeviceModel(DMObject):
    '''
    This is the complete representation of the ASA configuration in IFC model. The structure should be the same as
    device_specification.xml. Namely, at the top level, we have the
        - MFunc: the function configuration. In our case, it is "firewall"
        - MGrpCfg: the configuration shared by different functions.
          Not sure what it mean for ASA, since we have only one function now, that is "firewall".
        - MDevCfg: the configuration shared by all groups.
    The order to register the components is important, like in ASDM: that is the order to translate configuration
    from IFC format to ASA format.

    NOTE:
    The configuration structure of the device_specification.xml is based on "Insieme Service Management Integration"
    version 0.2. It is not quite in the final state yet, and is very likely to change.
    '''

    def __init__(self, device = None, interfaces = None, include_shared_config = True):
        '''
        @param device: dict
            to identify the ASA device, passed in from device_script APIs
        @param interfaces: dict
            physical interfaces names passed in from device_script APIs
        @param include_shared_config: boolean
            Flag to indicate if the function configuration should be modified.
        '''
        DMObject.__init__(self, ifc_key = DeviceModel.__name__)
        self.device = device
        self.interfaces = interfaces
        self.sts_table = {}
        self.label2nameif = {} #cache of label to nameif map

        'All the stuff defined in vnsMDevCfg section of device_specification.xml'
        self.register_child(Vifs())
        self.register_child(DMList('VLAN', Vlan))
        self.register_child(VxlanPort('vxlan_port'))
        self.register_child(NVE('NVE'))
        self.register_child(TVIs())
        self.register_child(DMList('ENCAPASS', EncapAss))
        self.register_child(DMList('InterfaceConfig', InterfaceConfig))
        self.register_child(PortChannelMembers())
        self.register_child(HostObjects())
        self.register_child(SubnetObjects())
        self.register_child(RangeObjects())
        self.register_child(FQDNObjects())
        self.register_child(ICMP4Objects())
        self.register_child(ICMP6Objects())
        self.register_child(ProtocolObjects())
        self.register_child(TCPObjects())
        self.register_child(UDPObjects())
        self.register_child(NetworkObjectGroups())
        self.register_child(ServiceObjectGroups())
        self.register_child(AccessListList())
        self.register_child(AccessListDeployment()) # Must follow AccessListList
        self.register_child(ClusterConfig())
        self.register_child(LoggingConfig())
        self.register_child(FailoverConfig())
        self.register_child(AccessGroupGlobal())
        self.register_child(Timeouts())
        self.register_child(BasicThreatDetection())
        self.register_child(AdvancedThreatDetection())
        self.register_child(ScanningThreatDetection())
        self.register_child(NetFlowObjects())
        self.register_child(IPAudit())

        self.register_child(NTP())
        self.register_child(DNS())
        self.register_child(SmartCallHome())
        self.register_child(GlobalServicePolicyContainer())

        'Child for vsnGrpCfg element'
        if include_shared_config:
            self.register_child(SharedConfig())

    def get_device(self):
        '@return the device parameter from device script API'
        return self.device

    def get_interfaces(self):
        """
        @attention:  It is recommended to use get_nameif instead of calling get_interfaces by applications.
        @return the interfaces parameter from device script API'
        """
        return self.interfaces

    def is_virtual(self):
        '@return True if this device is ASAv, otherwise false'
        return self.device.get('virtual', False) if self.device else False

    def get_failover_lan_interface(self):
        '''
        Get the interface for LAN based failover connection.
        '''
        return self.get_interface_name(InterfaceLabel.FailoverLan)

    def get_failover_link_interface(self):
        '''
        Get the interface for link(stateful) failover connection.
        '''
        return self.get_interface_name(InterfaceLabel.FailoverLink)

    def get_ClusterControLink_interface(self):
        '''
        Get cluster control link interface.
        '''
        return self.get_interface_name(InterfaceLabel.ClusterControLink)

    def get_mgmt_interface(self):
        return self.get_interface_name(InterfaceLabel.Mgmt)

    def get_interface_name(self, label):
        '@return the physical interface name of a given interface label'
        if not self.interfaces:
            return None
        if not label in (InterfaceLabel.External, InterfaceLabel.Internal,
                         InterfaceLabel.Mgmt, InterfaceLabel.Utility,
                         InterfaceLabel.FailoverLan, InterfaceLabel.FailoverLink,
                         InterfaceLabel.ClusterControLink):
            return None

        if self.label2nameif.has_key(label):# try to lookup the cache
            return self.label2nameif[label]

        hits = filter(lambda item: item[1]['label'] == label, self.interfaces.iteritems())
        if not hits:
            return None
        interface_name = hits[0][0][2]
        interface_name = interface_name.replace('_', '/')
        return interface_name

    def get_nameif(self, label):
        '@return the nameif of a given interface label'
        interface_name = self.get_interface_name(label)
        if not interface_name:
            return
        query_cmd = "show run interface " + interface_name + " | grep nameif"
        output_cli = self.query_asa(query_cmd)
        if output_cli and output_cli.strip().startswith('nameif '):
            nameif = output_cli.strip().split()[1]
            self.label2nameif[label] = nameif
            return nameif

    def get_external_nameif(self):
        'short-cut to get nameif for external interface'
        return self.get_nameif(InterfaceLabel.External)

    def get_internal_nameif(self):
        'short-cut to get nameif for internal interface'
        return self.get_nameif(InterfaceLabel.Internal)

    def get_mgmt_nameif(self):
        'short-cut to get nameif for management interface'
        return self.get_nameif(InterfaceLabel.Mgmt)

    def get_utility_nameif(self):
        'short-cut to get nameif for utility interface'
        return self.get_nameif(InterfaceLabel.Utility)

class SharedConfig(DMObject):
    '''
    This is the group configuration of ASA, assuming the name of "MGrpCfg" element in
    the device_specifcation is "GroupConfig".
    Add group configuration objects by call self.register_child(dmobj) in
    the constructor as it is done in DeviceModel.__init(self)__.
    '''

    def __init__(self):
        DMObject.__init__(self, SharedConfig.__name__)
        self.register_child(Firewalls())

###============= just for testing ====
if __name__ == '__main__':

    #test simple functional configuration with Timeouts
    config = {(Type.DEV, '', 4192): {
                 'transaction': 10000,
                 'state': 1,
                 'value': {
                            (Type.ENCAPASS, '', 'Firewall_outside_4113'): {
                                 'vif': "",
                                 'transaction': 10000,
                                 'encap': "",
                                 'state': 1},
                            (Type.VIF, '', 'Firewall_outside'): {
                                 'transaction': 10000,
                                 'cifs': {'FW1':'Port-channel1'},
                                 'state': 1},
                            (Type.ENCAP, '', '15364'): {
                                 'transaction': 10000,
                                 'type': 0,
                                 'state': 1,
                                 'tag': 0},
                            (Type.ENCAPASS, '', 'Firewall_outside_15364'): {
                                 'vif': "",
                                 'transaction': 10000,
                                 'encap': "",
                                 'state': 1},
                            (Type.ENCAP, '', '4113'): {
                                 'transaction': 10000,
                                 'type': 0,
                                 'state': 1,
                                 'tag': 0},
                           (Type.GRP, '', 4256): {
                                'transaction': 10000,
                                'value': {
                                    (Type.FUNC, 'Firewall', 'Node2'): {
                                        'transaction': 10000,
                                        'value': {
                                            (Type.CONN, 'external', 'C5'): {
                                               'transaction': 10000,
                                               'value': {},
                                               'state': 1},
                                            (Type.CONN, 'internal', 'C4'): {
                                              'transaction': 10000,
                                              'value': {},
                                              'state': 1}},
                                        'state': 1}},

                                  'state': 1}}}}
    asa = DeviceModel()

    def create_missing_ifc_delta(ifc_cfg):
        'Transformer to fill in the missing folders'
        asa.populate_model(ifc_cfg.keys()[0], ifc_cfg.values()[0])
        asa.create_missing_ifc_delta_cfg()
        return ifc_cfg

    def set_cfg_state_2_DESTROY(ifc_cfg):
        'Transformer to set the State of each entry to DETROY'
        set_cfg_state(ifc_cfg, State.DESTROY)
        return ifc_cfg

    ifc_cfg = massage_param_dict(asa, config,
                                 transformers=[set_cfg_state_2_DESTROY,
                                               create_missing_ifc_delta])

    from utils.util import pretty_dict
    print pretty_dict(ifc_cfg)

#    print("Test functional configuration  with Timeouts: %s"  % [str(x) for x in clis])

