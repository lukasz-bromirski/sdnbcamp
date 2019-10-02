'''
Created on Nov 14, 2013

Copyright (c) 2013 by Cisco Systems
@author: dli

This module is framework for the configuration of NetFlow reporting, Connection Limits.

1. How to configure them on ASA
All these functionalities are configured under policy-map CLI on ASA.

Take global policy for example: the configuration looks something like:
=== Start of configuration ==
policy-map global_default
 class connection_limits_default
    <sub-commands related to connection limits>
 class inspection_default
    <sub-commands related to inspection>
 class netflow_default>
    <sub-commands related to netflow report>

class-map connection_limits_default
   match <traffic to apply connection limits policy>

class-map inspection_default
   match <traffic to apply inspection policy>

class-map netwflow_default
   match <traffic to apply inspection policy>
== End of configuration ===

policy-map is actually just a building block, to activate the above policy-map as the system default, you need to
issue the following CLI:

service-policy global_policy global.

2. Modeling of the configuration on IFC
To make it easy for the administrator, we choose just expose the concepts directly related to the task of
configuring connection limits, inspection, and netflow reporting, and not exposing the concepts of
policy-map, class-map since they are just ASA mechanisms to achieve the results.

To configure them, administrator goes to "GlobalServicePolicy" folder under which we have the entries to:
  - enable/disable the service-policy
  - each policy from: connection limits, inspection, netfow, has its own folder which contains:
     - traffic selection
     - detailed setting

'''

import re
from base.simpletype import SimpleType
from base.dmobject import DMObject
from base.compositetype import CompositeType
from connection_limits import ConnectionLimitSubCommands
from inspection_settings import InspectionSubCommands
from ips_settings import IPSSubCommands
from netflow_objects import NetFlowSubCommands
from state_type import State, Type
from structured_cli import StructuredCommand
import firewall

class ServicePolicyContainer(DMObject):
    'Base class  "service-policy CLI" container for NetwFlow, Connection Limits, and Inspection'
    """Factory default from ASA 9.0(0)107:
        class-map inspection_default
        match default-inspection-traffic
        !
        !
        policy-map global_policy
        class inspection_default
          inspect dns preset_dns_map
          inspect ftp
          inspect h323 h225
          inspect h323 ras
          inspect rsh
          inspect rtsp
          inspect esmtp
          inspect sqlnet
          inspect skinny
          inspect sunrpc
          inspect xdmcp
          inspect sip
          inspect netbios
          inspect tftp
          inspect ip-options
        !
        service-policy global_policy global

     """
    def __init__(self, ifc_key = "GlobalServicePolicy", connector = None):
        DMObject.__init__(self, ifc_key = ifc_key)
        self.register_child(PolicyMap(connector))
        self.register_child(ServicePolicy(connector))

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        'Override the default implementation because the IFC model does not directly map to self.children'
        DMObject.populate_model(self, delta_ifc_key, delta_ifc_cfg_value)
        'Let PolicyMap share the configuration with this translator'
        policy_map = self.children.values()[0]
        policy_map.populate_model(delta_ifc_key, delta_ifc_cfg_value)

        'If the this configuration for this object is destroyed, destroy its ServicePolicy child as well'
        if self.delta_ifc_cfg_value['state'] != State.DESTROY:
            return
        service_policy = self.children.values()[1]
        service_policy.populate_model((Type.PARAM, service_policy.ifc_key,''), {'state': State.DESTROY})

    def mark_absent(self):
        'Mark the IFC configuration for this translator as absent, this is used for DESTROY operation'
        self.delta_ifc_key = Type.FOLDER, self.ifc_key, ''
        '"PolicyMap_state" entry is for our internal use only'
        self.delta_ifc_cfg_value = {'state': State.NOCHANGE, 'value': {}, 'PolicyMap_state': State.NOCHANGE}
        ancestor = self.get_ifc_delta_cfg_ancestor()
        if ancestor:
            ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value

    def create_missing_ifc_delta_cfg(self):
        """Override the default implementation to leave indicator for absence of IFC configuration.
        Reminder: the purpose of this method is to prepare for configuration delete operation
        in diff_ifc_asa method.

        Note on implementing State.DESTROY operation for deviceAudit API on this translator:

          For deviceAudit operation, the framework uses the absence of self.delta_ifc_cfg_value
        to indicate this translator does not have IFC configuration. However, we have to create
        self.delta_ifc_cfg_value for this particular translator.

        Question: So how do we tell if IFC does not have configuration for this translator?
        Answer: by introducing an special entry, named 'PolicyMap_state', in the value dictionary for this translator,
                so that the get_action method can use this entry in the self.delta_ifc_cfg_value, i.e.
                self.delta_ifc_cfg_value['PolicyMap_state'] to determine if the operation is State.DESTROY.
        """
        if self.has_ifc_delta_cfg():
            return DMObject.create_missing_ifc_delta_cfg(self)

        self.mark_absent()

        for child in self.children.values():
            child.create_missing_ifc_delta_cfg()

        'Let PolicyMap share the configuration with this translator'
        policy_map = self.children.values()[0]
        policy_map.populate_model(self.delta_ifc_key, self.delta_ifc_cfg_value)

class GlobalServicePolicyContainer(ServicePolicyContainer):
    """Model after global "service-policy CLI <name> global" container for global NetwFlow, Connection Limits, and Inspection
    """
    def __init__(self):
        ServicePolicyContainer.__init__(self)

class IntConnectorServicePolicyContainer(ServicePolicyContainer):
    'Model after service-policy for the internal connector'
    def __init__(self):
        ServicePolicyContainer.__init__(self, 'IntServicePolicy', 'internal')

class ExtConnectorServicePolicyContainer(ServicePolicyContainer):
    'Model after service-policy for the external connector'
    def __init__(self):
        ServicePolicyContainer.__init__(self, 'ExtServicePolicy', 'external')

class NameIf(object):
    'Provider of nameif from connector name'
    def __init__(self, connector):
        '@param connector: str, the name of a connector'
        self.connector = connector

    def get_nameif(self):
        '@return str: the nameif of the connector'
        if not self.connector:
            return None
        fw = self.get_ancestor_by_class(firewall.Firewall)
        connector = fw.get_connector(self.connector)
        """
        'It is possible for a connector to not have a nameif in the case where the IFC
        configuration does have the connector information under Firewall folder.
        """
        return connector.get_nameif() if connector else None

class ServicePolicy(SimpleType, NameIf):
    'Model after "service-policy" CLI'
    def __init__(self, connector = None):
        '@param connector: str, the name of a connector; None for global policy'
        SimpleType.__init__(self, ifc_key = 'ServicePolicyState', asa_key = "service-policy")
        NameIf.__init__(self, connector)

    def get_cli(self):
        'Override default to use fixed name'
        if self.connector:
            nameif = self.get_nameif()
            cmd_suffix = " %s interface %s" % (nameif, nameif)
        else:
            cmd_suffix = " global_policy global"
        return self.asa_key + cmd_suffix

    def is_my_cli(self, cli):
        'Override the default implementation to recognize "service-policy" as mine'
        cmd_suffix = " \S+ interface %s" % self.get_nameif() if self.connector else " \S+ global"
        regexp = self.asa_key + cmd_suffix
        return re.compile(regexp).match(str(cli))

    def is_the_same_cli(self, cli):
        """Simplify the implementation.
        @todo need to take care of fail-close suffix in the cli.
        """
        return self.get_cli() == cli

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        """Override default to map "enable" and "disable" value from IFC configuration to the corresponding CLI.
        Also issue "no " + old_cli in case it was bind to things other than 'global_default'
        """
        if not self.has_ifc_delta_cfg():
            return
        action = self.get_action()
        if action == State.NOCHANGE:
            return
        if action in (State.CREATE, State.MODIFY):
            value = self.get_value()
            if value == 'enable':
                self.generate_cli(asa_cfg_list, self.get_cli())
            else: #disable
                self.generate_cli(no_asa_cfg_stack, 'no ' + self.get_cli())
            ''
            old_cli = self.delta_ifc_cfg_value.get('old_cli', None)
            if old_cli:
                self.generate_cli(no_asa_cfg_stack, 'no ' + old_cli)
        elif action == State.DESTROY and self.is_removable:
            self.generate_cli(no_asa_cfg_stack, 'no ' + self.get_cli())

    def diff_ifc_asa(self, cli):
        'Override the default implementation to remember the old cli for deletion purpose'
        SimpleType.diff_ifc_asa(self, cli)
        self.delta_ifc_cfg_value['old_cli'] = cli

class _CompositeType(CompositeType, NameIf):
    'A specialized CompositeType where class-map is a global command rather than sub-command'

    def __init__(self, ifc_key, connector):
        '@param connector: str, the name of a connector; None for global policy'
        CompositeType.__init__(self, ifc_key = ifc_key)
        NameIf.__init__(self, connector)

    def get_translator(self, cli):
        'Override the default implementation to take care of global class-map command'
        if not self.asa_key and hasattr(self, 'create_asa_key'):
            self.asa_key = self.create_asa_key()
        if not self.asa_key:
            return None

        if self.is_my_cli(cli):
            return self
        if isinstance(cli, str):
            command = cli.strip()
        elif isinstance(cli, StructuredCommand):
            command =  cli.command.strip()
        if command.startswith('class-map '):
            for child in self.children.values():
                result = child.get_translator(cli)
                if result:
                    return result
        return None

class PolicyMap(_CompositeType):
    'Model after "policy-map" CLI for netflow and connection limits.'
#     def __init__(self,  name, connector = None):
    def __init__(self, connector = None):
        _CompositeType.__init__(self, ifc_key = PolicyMap.__name__, connector = connector)
        '@param connector: str, the name of a connector, None if global'

        self.register_child(ConnectionLimits(connector))
        self.register_child(Inspection(connector))
        self.register_child(NetFlow(connector))
        self.register_child(IPS(connector))

    def create_asa_key(self):
        '@return str as the asa key'
        name = self.get_nameif() if self.connector else "global_policy"
        return "policy-map " + name if name else None

    def get_cli(self):
        'Override the default because self.asa_key is run-time information'
        self.asa_key = self.create_asa_key()
        return self.asa_key

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        '''Override the default implementation to take care of the special 'sub-command'
        class-map, which is actually a global-command.
        '''
        if not self.has_ifc_delta_cfg():
            return

        if self.get_action() == State.DESTROY:
            'To generate the no form of the command'
            for child in self.children.values(): #taking care of removing class-map global command
                child.ifc2asa(no_asa_cfg_stack, asa_cfg_list)
            SimpleType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)
            return

        _CompositeType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def create_missing_ifc_delta_cfg(self):
        'Override the default implementation to not leave trace of PolicyMap in IFC configuration because we share it with the parent'
        for child in self.children.values():
            child.create_missing_ifc_delta_cfg()

    def get_action(self):
        'Override the default implementation to use "PolicyMap_sate" entry in the dictionary for DESTROY operation.'
        if self.delta_ifc_cfg_value.has_key('PolicyMap_state'):# not present in IFC
            return self.delta_ifc_cfg_value['PolicyMap_state']
        return self.delta_ifc_cfg_value['state']

    def diff_ifc_asa(self, cli):
        'Since it shares IFC configuration with its parent, no need to create a folder for it in the delete operation'
        assert self.has_ifc_delta_cfg()
        if self.delta_ifc_cfg_value.has_key('PolicyMap_state'):# not present in IFC
            self.delta_ifc_cfg_value['PolicyMap_state'] = State.DESTROY
        else:
            _CompositeType.diff_ifc_asa(self, cli)

class ClassMap(CompositeType):
    'Model after class-map global command only deal with "match" sub-command. This is only used in service-policy!'
    def __init__(self):
        'Pass down the value of TrafficSelector to the sub-command'
        CompositeType.__init__(self, ifc_key = 'TrafficSelection')
        self.register_child(TrafficSelection())

    def create_asa_key(self):
        '@return asa key at run time'
        if self.parent.connector and not self.parent.get_nameif():
            return None
        return "class-map " + self.get_parent().create_class_map_name()

    def get_cli(self):
        self.asa_key = self.create_asa_key()
        return self.asa_key

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        'Override the default implementation to push the value down to the child'
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.children.values()[0].populate_model(delta_ifc_key, delta_ifc_cfg_value)

    def create_missing_ifc_delta_cfg(self):
        'Override the default implementation to do nothing because it does not have an explicit folder in IFC configuration.'
        pass

class TrafficSelection(SimpleType):
    'Model after class-map global command only deal with "match" sub-command. This is only used in service-policy!'
    def __init__(self):
        SimpleType.__init__(self, ifc_key='TrafficSelection', asa_key='match', defaults='any')

    def diff_ifc_asa(self, cli):
        'Override the default implementation to remember the old cli for deletion purpose'
        SimpleType.diff_ifc_asa(self, cli)
        self.delta_ifc_cfg_value['old_cli'] = cli

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        '''Override the default implementation for modify action:
        Need to issue no command to delete old one and then issue command to set the new one.
        '''
        if self.get_action() == State.MODIFY:
            old_cli = self.get_old_cli()
            if old_cli:
                self.generate_cli(no_asa_cfg_stack, 'no ' + old_cli)
        SimpleType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def get_old_cli(self):
        '@return the old CLI for modification operation.'
        old_cli = self.delta_ifc_cfg_value.get('old_cli')
        if old_cli:
            return old_cli
        query_cmd = "show run " + self.parent.get_cli() + " | grep match"
        old_cli = self.query_asa(query_cmd)
        return old_cli.strip() if old_cli else None

    def parse_single_parameter_cli(self, cli):
        '''Override the implementation to return anything after 'match' as the value.
        For now, we support the following forms:
             match any
             match access-list <name>
             match default-inspection-traffic
        '''
        return ' '.join(cli.split()[1:])

class _ClassSubCommand(_CompositeType):
    'Model after "class" sub-command for connection limits, netflow or inspection under policy-map command'
    def __init__(self, ifc_key, connector, class_map_name_prefix, sub_command_translator):
        '@param connector: str, the name of a connector'
        _CompositeType.__init__(self, ifc_key = ifc_key, connector = connector)
        self.class_map_name_prefix = class_map_name_prefix
        self.register_child(ClassMap())
        self.register_child(sub_command_translator)

    def create_class_map_name(self):
        '@return str: the class-map name. The value is based on connector nameif'
        class_map_name_suffix = self.get_nameif() if self.connector else "default"
        class_map_name = self.class_map_name_prefix + class_map_name_suffix
        return class_map_name

    def create_asa_key(self):
        '@return str as the asa key'
        if self.connector and not self.get_nameif():
            return None
        return "class " + self.create_class_map_name()

    def get_cli(self):
        'Override the default because self.asa_key is run-time information'
        self.asa_key = self.create_asa_key()
        return self.asa_key

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        '''Override the default implementation to take care of the class-map command which is global rather than sub-command.
        '''
        if not self.has_ifc_delta_cfg():
            return

        class_map = self.children.values()[0]
        sub_commands = self.children.values()[1]
        if self.get_action() == State.DESTROY:
            'To generate the no form of the command, rid of class-map global command, no need to issue "no class" sub-command'
            class_map.ifc2asa(no_asa_cfg_stack, asa_cfg_list)
            'Only issue "no class" command if we modify the policy-map rather than destroy the policy-map'
            if self.parent.get_action() != State.DESTROY:
                SimpleType.ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list)
            return

        'Generate CLIs from the children, class_map is a global command.'
        class_map.ifc2asa(no_asa_cfg_stack, asa_cfg_list);
        sub_commands.mode_command = self.get_child_mode_command()
        sub_commands.ifc2asa(no_asa_cfg_stack, asa_cfg_list);

    def get_sub_commands(self):
        """Override the default implementation to exclude class-map command because it is global rather than sub-command.
        It is used by is_the_same_cli method.
        """
        result = []
        for child in self.children.values():
            if isinstance(child, ClassMap):
                continue
            if hasattr(child, 'get_cli'):
                result.append(child.get_cli())
            for grand_child in child.children.values():
                if grand_child.has_ifc_delta_cfg():
                    result.append(grand_child.get_cli())
        return result


class ConnectionLimits(_ClassSubCommand):
    'Model after "class" sub-command for connection limits under policy-map command'
    def __init__(self, connector):
        '@param connector: str, the name of a connector'
        _ClassSubCommand.__init__(self,
                                  ifc_key = "ConnectionLimits",
                                  connector = connector,
                                  class_map_name_prefix = "connection_limits_",
                                  sub_command_translator = ConnectionLimitSubCommands())

class NetFlow(_ClassSubCommand):
    'Model after "class" sub-command for NetFlow policy-map command'
    def __init__(self, connector):
        '@param connector: str, the name of a connector'
        _ClassSubCommand.__init__(self,
                                  ifc_key = "NetFLow",
                                  connector = connector,
                                  class_map_name_prefix = "netflow_",
                                  sub_command_translator = NetFlowSubCommands())

class Inspection(_ClassSubCommand):
    'Model after "class" sub-command for Inspection policy-map command'
    def __init__(self, connector):
        '@param connector: str, the name of a connector'
        _ClassSubCommand.__init__(self,
                                  ifc_key = "ApplicationInspection",
                                  connector = connector,
                                  class_map_name_prefix = "inspection_",
                                  sub_command_translator = InspectionSubCommands())

class IPS(_ClassSubCommand):
    'Model after "class" sub-command for IPS policy-map command'
    def __init__(self, connector):
        '@param connector: str, the name of a connector'
        _ClassSubCommand.__init__(self,
                                  ifc_key = "IPS",
                                  connector = connector,
                                  class_map_name_prefix = "ips_",
                                  sub_command_translator = IPSSubCommands())