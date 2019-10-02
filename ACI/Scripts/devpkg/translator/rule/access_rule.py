'''
Created on Jul 15, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Classes used for access rules.
'''

import re

from asaio.cli_interaction import ignore_response_parser
from asaio.cli_interaction import ignore_warning_response_parser
import translator
from translator.base.dmlist import DMList
from translator.base.dmobject import DMObject
from translator.base.simpletype import SimpleType
from translator.state_type import State, Type
from translator.validators import ICMPValidator
from translator.validators import ProtocolValidator, TCPUDPValidator
import utils.protocol
from utils.service import get_icmp_type_cli, get_port_cli
from utils.util import normalize_param_dict, ifcize_param_dict


class AccessGroup(SimpleType):
    'A single access group'

    def __init__(self, instance):
        SimpleType.__init__(
            self,
            ifc_key=instance,
            asa_key='access-group',
            asa_gen_template='access-group %(access_list_name)s %(direction)s interface %(interface_name)s')

    def get_cli(self):
        values = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        interface_name = self.parent.get_interface_name()
        if interface_name:
            values['interface_name'] = interface_name

        return self.asa_gen_template % values

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if self.get_state() == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack,
                              'no ' + self.get_cli(),
                              response_parser=ignore_response_parser)
        else:
            super(AccessGroup, self).ifc2asa(no_asa_cfg_stack, asa_cfg_list)

class AccessGroupList(DMList):
    'A list of access groups bound to a connector'

    MY_CLI_PATTERN = None

    def __init__(self, name, connector_name):
        DMList.__init__(self, name, AccessGroup, 'access-group')
        self.connector_name = connector_name

    def get_interface_name(self):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(self.connector_name)
        if connector:
            return connector.get_nameif()

    def get_my_cli_pattern(self):
        if not self.MY_CLI_PATTERN:
            self.MY_CLI_PATTERN = re.compile('access-group \S+ \S+ interface (\S+)$')
        return self.MY_CLI_PATTERN

    def is_my_cli(self, cli):
        if isinstance(cli, basestring):
            m = self.get_my_cli_pattern().match(cli.strip())
            if m:
                return m.group(1) == self.get_interface_name()

class AccessGroupGlobal(SimpleType):
    'The single global access group'

    MY_CLI_PATTERN = None

    def __init__(self):
        SimpleType.__init__(
            self,
            ifc_key=AccessGroupGlobal.__name__,
            asa_key='access-group',
            asa_gen_template='access-group %(access_list_name)s global')

    def get_my_cli_pattern(self):
        if not self.MY_CLI_PATTERN:
            self.MY_CLI_PATTERN = re.compile('access-group \S+ global$')
        return self.MY_CLI_PATTERN

    def is_my_cli(self, cli):
        if isinstance(cli, basestring):
            return self.get_my_cli_pattern().match(cli.strip())

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if self.get_state() == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack,
                              'no ' + self.get_cli(),
                              response_parser=ignore_response_parser)
        else:
            super(AccessGroupGlobal, self).ifc2asa(no_asa_cfg_stack,
                                                   asa_cfg_list)

class AccessControlEntry(DMObject):
    'A single access control entry (ACE)'

    # CLI syntax:
    #     access-list <name> extended <action> <protocol> <source-ip>
    #         <source-mask> [<dest-operator> <dest-low-port> [<dest-high-port>]]
    #
    # Examples:
    #     access-list global_access extended deny ip any any
    #     access-list global_access extended deny object ldap_server any any
    #     access-list global_access extended deny object-group web_server any any
    #     access-list global_access extended deny tcp any any eq 5006
    #     access-list global_access extended deny tcp any any range 5001 5002
    ANY_CLI_PATTERN = None
    ICMP_CLI_PATTERN = None
    TCP_UDP_CLI_PATTERN = None

    def __init__(self, instance):
        DMObject.__init__(self, ifc_key=instance)
        self.defaults = {
            'protocol': {'name_number': 'ip'},
            'source_address': {'any': 'any'},
            'destination_address': {'any': 'any'}
        }

    def set_action(self, state):
        self.delta_ifc_cfg_value['state'] = state

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            self.delta_ifc_key = (Type.FOLDER, AccessControlEntry.__name__, cli)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': ifcize_param_dict(self.values)}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            if ancestor:
                ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value

    def equals_no_order(self, ace):
        ace_values = ace.values.copy()
        if 'order' in ace_values:
            del ace_values['order']
        self_values = self.values.copy()
        if 'order' in self_values:
            del self_values['order']

        return self_values == ace_values

    def get_cli(self, line_no=None):
        cli = []
        cli.append('access-list ' + self.parent.ifc_key)
        if line_no:
            cli.append(' line ' + str(line_no))
        cli.append(' extended ' + self.values['action'])
        self.append_protocol(cli, self.values['protocol'])
        self.append_address(cli, self.values.get('source_address'))
        if self.is_tcp_udp():
            self.append_service(cli, self.values.get('source_service'))
        self.append_address(cli, self.values.get('destination_address'))
        if self.is_tcp_udp():
            self.append_service(cli, self.values.get('destination_service'))
        elif self.is_icmp():
            self.append_icmp(cli, self.values.get('icmp'))

        return ''.join(cli)

    def is_icmp(self):
        return self.values['protocol'].get('name_number') in ('icmp', 'icmp6')

    def is_tcp_udp(self):
        return self.values['protocol'].get('name_number') in ('tcp', 'udp')

    def set_acl_changed(self):
        self.parent.set_acl_changed()

    @staticmethod
    def append_address(cli, address):
        if 'any' in address:
            cli.append(' ' + address['any'])
        elif 'object_name' in address:
            cli.append(' object ' + address['object_name'])
        elif 'object_group_name' in address:
            cli.append(' object-group ' + address['object_group_name'])

    @staticmethod
    def append_icmp(cli, icmp):
        if icmp:
            cli.append(' ' + icmp['type'])
            if 'code' in icmp:
                cli.append(' ' + icmp['code'])

    @staticmethod
    def append_protocol(cli, protocol):
        if 'name_number' in protocol:
            cli.append(' ' + protocol['name_number'])
        elif 'object_name' in protocol:
            cli.append(' object ' + protocol['object_name'])
        elif 'object_group_name' in protocol:
            cli.append(' object-group ' + protocol['object_group_name'])

    @staticmethod
    def append_service(cli, service):
        if service:
            cli.append(' ' + service['operator'] + ' ' + service['low_port'])
            if service['operator'] == 'range':
                cli.append(' ' + service['high_port'])

    def generate_command(self, asa_cfg_list, line_no=None):
        self.generate_cli(asa_cfg_list,
                          self.get_cli(line_no),
                          response_parser=ignore_warning_response_parser)
        self.set_acl_changed()

    def generate_delete(self, asa_cfg_list):
        self.generate_cli(asa_cfg_list,
                          'no ' + self.get_cli(),
                          response_parser=ignore_response_parser)
        self.set_acl_changed()

    @classmethod
    def parse_cli(cls, cli, order=None):
        result = cls.parse_tcp_udp_cli(cli, order)
        if not result:
            result = cls.parse_icmp_cli(cli, order)
        if not result:
            result = cls.parse_any_cli(cli, order)
        return result

    @classmethod
    def get_any_cli_pattern(cls):
        'For any type of traffic, no ports'

        if not cls.ANY_CLI_PATTERN:
            cls.ANY_CLI_PATTERN = re.compile(
                'access-list \S+ extended' +
                ' (\S+)' +                                          # Action, group 1
                ' (?:(object|object-group) )?(\S+)' +               # Protocol, groups 2,3
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))' + # Source address, groups 4,5,6
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))')  # Destination address, groups 7,8,9
        return cls.ANY_CLI_PATTERN

    @classmethod
    def parse_any_cli(cls, cli, order):
        'For any type of traffic, no ports'

        m = cls.get_any_cli_pattern().match(cli)
        if m:
            result = {}
            if order:
                result['order'] = str(order)
            result['action'] = m.group(1)
            cls.parse_protocol(result, *m.group(2, 3))
            cls.parse_address(result, 'source_address', *m.group(4, 5, 6))
            cls.parse_address(result, 'destination_address', *m.group(7, 8, 9))
            return result

    @classmethod
    def get_icmp_cli_pattern(cls):
        'For ICMP traffic, with ICMP type'

        if not cls.ICMP_CLI_PATTERN:
            cls.ICMP_CLI_PATTERN = re.compile(
                'access-list \S+ extended' +
                ' (\S+)' +                                          # Action, group 1
                ' (icmp[6]?)' +                                     # Protocol, group 2
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))' + # Source address, groups 3,4,5
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))' + # Destination address, groups 6,7,8
                '(?: (\S+)(?: (\S+))?)?')                           # ICMP information, groups 9,10
        return cls.ICMP_CLI_PATTERN

    @classmethod
    def parse_icmp_cli(cls, cli, order):
        'For ICMP traffic, with ICMP type'

        m = cls.get_icmp_cli_pattern().match(cli)
        if m:
            result = {}
            if order:
                result['order'] = str(order)
            result['action'] = m.group(1)
            result['protocol'] = {'name_number': m.group(2)}
            cls.parse_address(result, 'source_address', *m.group(3, 4, 5))
            cls.parse_address(result, 'destination_address', *m.group(6, 7, 8))
            cls.parse_icmp(result, *m.group(9, 10))
            return result

    @classmethod
    def get_tcp_udp_cli_pattern(cls):
        'For TCP or UDP traffic, with ports'

        if not cls.TCP_UDP_CLI_PATTERN:
            cls.TCP_UDP_CLI_PATTERN = re.compile(
                'access-list \S+ extended' +
                ' (\S+)' +                                          # Action, group 1
                ' (tcp|udp)' +                                      # Protocol, group 2
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))' + # Source address, groups 3,4,5
                '(?: (lt|gt|eq|neq|range) (\S+)(?: (\S+))?)?' +     # Source service, groups 6,7,8
                ' (?:(any[46]?)|(?:(object|object-group) (\S+)))' + # Destination address, groups 9,10,11
                '(?: (lt|gt|eq|neq|range) (\S+)(?: (\S+))?)?')      # Destination service, groups 12,13,14
        return cls.TCP_UDP_CLI_PATTERN

    @classmethod
    def parse_tcp_udp_cli(cls, cli, order):
        'For TCP or UDP traffic, with ports'

        m = cls.get_tcp_udp_cli_pattern().match(cli)
        if m:
            result = {}
            if order:
                result['order'] = str(order)
            result['action'] = m.group(1)
            result['protocol'] = {'name_number': m.group(2)}
            cls.parse_address(result, 'source_address', *m.group(3, 4, 5))
            cls.parse_service(result, 'source_service', *m.group(6, 7, 8))
            cls.parse_address(result, 'destination_address', *m.group(9, 10, 11))
            cls.parse_service(result, 'destination_service', *m.group(12, 13, 14))
            return result

    @staticmethod
    def parse_address(result, key, any_address, keyword, name):
        if any_address:
            result[key] = {'any': any_address}
        if keyword:
            address = {}
            if keyword == 'object':
                address['object_name'] = name
            elif keyword == 'object-group':
                address['object_group_name'] = name
            result[key] = address

    @staticmethod
    def parse_icmp(result, type_name, code):
        if type_name:
            icmp = {'type': type_name}
            if code:
                icmp['code'] = code
            result['icmp'] = icmp

    @staticmethod
    def parse_protocol(result, keyword, name):
        protocol = {}
        if keyword:
            if keyword == 'object':
                protocol['object_name'] = name
            elif keyword == 'object-group':
                protocol['object_group_name'] = name
        else:
            protocol['name_number'] = name
        result['protocol'] = protocol

    @staticmethod
    def parse_service(result, key, operator, low_port, high_port):
        if operator:
            service = {'operator': operator, 'low_port': low_port}
            if high_port:
                service['high_port'] = high_port
            result[key] = service

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        super(AccessControlEntry, self).populate_model(
            delta_ifc_key, delta_ifc_cfg_value)
        self.values = normalize_param_dict(self.delta_ifc_cfg_value['value'])

        # Populate defaults
        for name, default in self.defaults.iteritems():
            self.values.setdefault(name, default)

        self.normalize_protocol(self.values['protocol'])
        self.normalize_service(self.values['protocol'], self.values.get('source_service'))
        self.normalize_service(self.values['protocol'], self.values.get('destination_service'))
        self.normalize_icmp(self.values['protocol'], self.values.get('icmp'))

    @staticmethod
    def normalize_icmp(protocol, icmp):
        'Replace icmp type with its CLI equivalent'
        if icmp and 'name_number' in protocol:
            icmp['type'] = get_icmp_type_cli(protocol['name_number'], icmp['type'])

    @staticmethod
    def normalize_protocol(protocol):
        'Replace protocol with its CLI equivalent'
        if 'name_number' in protocol:
            protocol['name_number'] = utils.protocol.get_cli(protocol['name_number'])

    @staticmethod
    def normalize_service(protocol, service):
        'Replace service port with its CLI equivalent'
        if service and 'name_number' in protocol:
            protocol_name = protocol['name_number']
            service['low_port'] = get_port_cli(protocol_name, service['low_port'])
            if 'high_port' in service:
                service['high_port'] = get_port_cli(protocol_name, service['high_port'])

    def validate_configuration(self):
        if self.get_state() == State.MODIFY:
            return self.generate_fault(self.NOT_MODIFIABLE_ERROR)

        faults = []
        self.validate_protocol(faults)
        for folder in ('source_address', 'destination_address'):
            self.validate_address(faults, folder)
        self.validate_service(faults)
        self.validate_icmp(faults)
        return faults

    def validate_address(self, faults, folder):
        address = self.values[folder]
        if len(address) > 1:
            faults.append(self.generate_fault(
                folder + ' can only contain one of any, object_name, or object_group_name.',
                folder))
            return

    def validate_icmp(self, faults):
        icmp = self.values.get('icmp')
        if icmp:
            if not self.is_icmp():
                faults.append(self.generate_fault(
                    'Only supported for a protocol of icmp or icmp6.', 'icmp'))
                return

            protocol = self.values['protocol'].get('name_number')
            validator = ICMPValidator(protocol, 'icmp')
            validator.generate_fault = self.generate_fault
            faults.extend(validator.validate(icmp))

    def validate_protocol(self, faults):
        protocol = self.values['protocol']
        if len(protocol) > 1:
            faults.append(self.generate_fault(
                'protocol can only contain one of name_number, object_name, or object_group_name.',
                'protocol'))
            return
        if 'name_number' in protocol:
            err_msg = ProtocolValidator().validate(protocol['name_number'])
            if err_msg:
                faults.append(self.generate_fault(
                    err_msg, ['protocol', 'name_number']))

    def validate_service(self, faults):
        if 'source_service' in self.values or 'destination_service' in self.values:
            if not self.is_tcp_udp():
                for key in ('source_service', 'destination_service'):
                    if key in self.values:
                        faults.append(self.generate_fault(
                            'Only supported for a protocol of tcp or udp.',
                            key))
                return

            protocol = self.values['protocol'].get('name_number')
            validator = TCPUDPValidator(protocol, 'source_service', 'destination_service')
            validator.generate_fault = self.generate_fault
            faults.extend(validator.validate(self.values))

    def __str__(self):
        return self.get_cli()

class AccessList(DMList):
    'A single access list that contains access control entries (ACE)'

    def __init__(self, instance):
        DMList.__init__(self, instance, AccessControlEntry, 'access-list')
        self.diff_ifc_asa_ace_order = 1

    def set_action(self, state):
        self.delta_ifc_cfg_value['state'] = state

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            self.delta_ifc_key = (Type.FOLDER, self.parent.ifc_key, self.ifc_key)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': {}}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            if ancestor:
                ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
        elif self.delta_ifc_cfg_value['state'] != State.DESTROY:
            values = AccessControlEntry.parse_cli(cli, self.diff_ifc_asa_ace_order)
            if values:
                self.set_action(State.MODIFY)

                ace = AccessControlEntry(cli)
                ace.values = values
                self.diff_ifc_asa_ace_order += 1

                match_ace = self.find_ace(ace)
                if match_ace:
                    match_ace.set_action(State.NOCHANGE)
                else:
                    # Delete the ACE if it doesn't exist or is in a different order
                    self.register_child(ace)
                    ace.diff_ifc_asa(cli)

    def find_ace(self, ace):
        for match_ace in self.children.itervalues():
            if match_ace.values == ace.values:
                return match_ace

    def generate_delta(self, no_asa_cfg_stack, asa_cfg_list):
        'Optimize the generated CLI by looking for ACEs that have moved'

        # Split into old and new config
        old_config = []
        new_config = []
        for ace in self.children.itervalues():
            state = ace.delta_ifc_cfg_value['state']
            if state == State.NOCHANGE:
                old_config.append(ace)
                new_config.append(ace)
            elif state == State.CREATE:
                new_config.append(ace)
            elif state == State.DESTROY:
                old_config.append(ace)

        # Sort the old and new config
        old_config.sort(key=lambda ace: int(ace.values['order']))
        new_config.sort(key=lambda ace: int(ace.values['order']))

        # List of new positions corresponding to the old positions.  e.g. if the
        # first ACE in the old config is now in position 4 of the new config,
        # then new_positions[0] == 4
        new_positions = []

        # The element at old_positions[i] is equal to the element at
        # new_positions[i].  This is used to keep track of what has changed
        # during the traversal of the old config for optimizing the CLI when
        # traversing the new config 
        old_positions = []

        # List of old positions that have been deleted
        delete_old_positions = []

        for i, ace in enumerate(old_config):
            pos = AccessList.equal_ace_position(new_config, ace)
            if pos < 0:
                delete_old_positions.append(i)
            else:
                new_positions.append(pos)
                old_positions.append(i)

        # Handle the case where all the ACEs in an access list have been either
        # deleted or moved.  Normally, all the ACEs would first be deleted and
        # then the changed ones would be added back.  However, if the access
        # list is in use, then the ASA will delete all polices using the access
        # list when the last ACE is deleted.  To get around this, the first
        # changed ACE is added before any ACEs are deleted. 
        is_rebuilt = (len(delete_old_positions) == len(old_config) and
                      len(new_config) > 0)

        # Delete what was moved and what was deleted
        what_moved = AccessList.what_moved(new_positions)
        for i in what_moved:
            delete_old_positions.append(old_positions[new_positions.index(i)])
        for i in delete_old_positions:
            old_config[i].generate_delete(no_asa_cfg_stack)

        # If the access list is rebuilt, add the first changed ACE to the end
        # of the 'no' CLI list.  After the 'no' list is reversed, the first
        # changed ACE will be before any ACEs to be removed.
        if is_rebuilt:
            new_config[0].generate_command(no_asa_cfg_stack, line_no=1)

        # Add what was added or moved
        start = 1 if is_rebuilt else 0
        for i, ace in enumerate(new_config[start:], start):
            if i not in new_positions or i in what_moved:
                ace.generate_command(asa_cfg_list, line_no=i + 1)

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        state = self.get_state()
        if state in (State.CREATE, State.MODIFY):
            if state == State.CREATE:
                # Sort the ACEs into order
                access_control_entries = list(self.children.itervalues())
                access_control_entries.sort(
                    key=lambda ace: int(ace.values['order']))
                for ace in access_control_entries:
                    ace.generate_command(asa_cfg_list)
            else:
                self.generate_delta(no_asa_cfg_stack, asa_cfg_list)
        elif state == State.DESTROY:
            self.generate_cli(
                no_asa_cfg_stack,
                'clear config access-list ' + self.ifc_key,
                response_parser=ignore_response_parser)
            self.set_acl_changed()

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        for key, value in delta_ifc_cfg_value['value'].iteritems():
            super(AccessList, self).populate_model(key, value)

    def set_acl_changed(self):
        access_list_deployment = self.get_top().get_child('AccessListDeployment')
        if access_list_deployment:
            access_list_deployment.set_acl_changed()

    @staticmethod
    def equal_ace_position(new_config, old_ace):
        'Find position of the ACE in the new config'
        for i, new_ace in enumerate(new_config):
            if new_ace.equals_no_order(old_ace):
                return i
        return -1

    @staticmethod
    def longest_increasing_subsequence(x):
        '''
        Finds the longest increasing subsequence of the specified sequence.

        The subsequence is in sorted order (lowest to highest) and is as long as
        possible.  The subsequence is not necessarily contiguous.

        As an example, for the following sequence:
            1,2,0,3,4,5,6
        the longest increasing subsequence is:
            1,2,3,4,5,6
        '''

        if not x:
            return []

        best = [0]
        pred = [0] * len(x)
        for i in xrange(1, len(x)):
            if cmp(x[best[-1]], x[i]) < 0:
                pred[i] = best[-1]
                best.append(i)
                continue

            low = 0
            high = len(best) - 1
            while low < high:
                mid = (low + high) / 2
                if cmp(x[best[mid]], x[i]) < 0:
                    low = mid + 1
                else:
                    high = mid

            if cmp(x[i], x[best[low]]) < 0:
                if low > 0:
                    pred[i] = best[low -1]
                best[low] = i

        result = []
        j = best[-1]
        for i in xrange(len(best)):
            result.insert(0, x[j])
            j = pred[j]
        return result

    @staticmethod
    def what_moved(positions):
        if len(positions) <= 1:
            return []

        sequence = AccessList.longest_increasing_subsequence(positions)
        moved_positions = []
        for i in positions:
            if i not in sequence:
                moved_positions.append(i)
        return moved_positions

class AccessListDeployment(DMObject):
    'Options for deploying access lists'

    def __init__(self):
        DMObject.__init__(self, AccessListDeployment.__name__)
        self.acl_changed = False

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if (not self.has_ifc_delta_cfg() or
                self.delta_ifc_cfg_value['state'] == State.DESTROY):
            return

        values = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if 'clear_translation' in values and self.acl_changed:
            self.generate_cli(asa_cfg_list, 'clear xlate')

    def set_acl_changed(self):
        self.acl_changed = True

class AccessListList(DMList):
    'A list of access lists'

    NAME_PATTERN = None

    def __init__(self):
        DMList.__init__(self, 'AccessList', AccessList, 'access-list')

    def get_name_pattern(self):
        if not self.NAME_PATTERN:
            # Extract the access list name
            self.NAME_PATTERN = re.compile('access-list (\S+) .*')
        return self.NAME_PATTERN

    def get_translator(self, cli):
        if isinstance(cli, basestring):
            m = self.get_name_pattern().match(cli.strip())
            if m:
                name = m.group(1)
                acl = self.get_child(name)
                if not acl:
                    acl = self.child_class(name)
                    self.register_child(acl)
                return acl
