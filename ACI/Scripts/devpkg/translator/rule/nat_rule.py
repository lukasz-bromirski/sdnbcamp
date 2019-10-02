'''
Created on Oct 28, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Classes used for NAT rules.
'''

import re

from asaio.cli_interaction import CLIInteraction, ignore_response_parser
from asaio.cli_interaction import ignore_warning_response_parser
import translator
from translator.state_type import State, Type
from translator.base.dmlist import DMList
from translator.base.dmobject import DMObject
from utils.util import ifcize_param_dict, normalize_param_dict 

class NATRule(DMObject):
    'A single NAT rule'

    CLI_PATTERN = None
    DEFAULTS = {'source_translation': {'nat_type': 'static'}}

    def __init__(self, instance):
        DMObject.__init__(self, ifc_key=instance)

    def set_action(self, state):
        self.delta_ifc_cfg_value['state'] = state

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            self.delta_ifc_key = (Type.FOLDER, NATRule.__name__, cli)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': ifcize_param_dict(self.values)}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            if ancestor:
                ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value

    def equals_no_order(self, nat):
        nat_values = nat.values.copy()
        if 'order' in nat_values:
            del nat_values['order']
        self_values = self.values.copy()
        if 'order' in self_values:
            del self_values['order']

        return self_values == nat_values

    def add_xlate(self, nat):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        if firewall:
            nat_rule_deployment = firewall.get_child('NATRuleDeployment')
            if nat_rule_deployment:
                nat_rule_deployment.add_xlate(nat)

    def generate_clear_xlate(self):
        cli = 'clear xlate interface ' + self.parent.get_interface_name('internal')
        return CLIInteraction(cli, model_key=self.get_config_path())

    def generate_command(self, asa_cfg_list):
        self.generate_cli(asa_cfg_list,
                          self.get_cli(),
                          response_parser=ignore_warning_response_parser)

    def generate_delete(self, asa_cfg_list):
        self.generate_cli(asa_cfg_list,
                          'no ' + self.get_cli(),
                          response_parser=ignore_response_parser)
        self.add_xlate(self)

    def get_cli(self):
        cli = []
        cli.append(self.parent.get_cli_prefix())
        self.append_source_address(cli, self.values.get('source_translation'))
        self.append_destination_address(cli, self.values.get('destination_translation'))
        self.append_service(cli, self.values.get('service_translation'))
        if 'dns' in self.values:
            cli.append(' dns')
        if 'unidirectional' in self.values:
            cli.append(' unidirectional')

        return ''.join(cli)

    def append_destination_address(self, cli, address):
        if address:
            cli.append(' destination static')
            cli.append(' ' + address.get('mapped_object_name', ''))
            cli.append(' ' + address.get('real_object_name', 'any'))

    def append_service(self, cli, service):
        if service:
            cli.append(' service')
            cli.append(' ' + service.get('real_object_name', 'any'))
            cli.append(' ' + service.get('mapped_object_name', ''))

    def append_source_address(self, cli, address):
        cli.append(' source')
        cli.append(' ' + address['nat_type'])
        cli.append(' ' + address.get('real_object_name', 'any'))
        cli.append(' ' + address.get('mapped_object_name', 'any'))

    @classmethod
    def populate_defaults(cls, values, defaults):
        for name, default in defaults.iteritems():
            if name in values:
                if isinstance(values[name], dict) and isinstance(default, dict):
                    cls.populate_defaults(values[name], default)
            else:
                values[name] = default

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        super(NATRule, self).populate_model(delta_ifc_key, delta_ifc_cfg_value)
        self.values = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        self.populate_defaults(self.values, self.DEFAULTS)

        # Normalize parameters whose values are ignored
        for param in ('dns', 'unidirectional'):
            if param in self.values:
                self.values[param] = None

    def validate_configuration(self):
        if self.get_state() == State.MODIFY:
            return self.generate_fault(self.NOT_MODIFIABLE_ERROR)

        faults = []
        self.validate_dns(faults)
        self.validate_unidirectional(faults)
        return faults

    def validate_dns(self, faults):
        if 'dns' in self.values:
            if 'destination_translation' in self.values:
                faults.append(self.generate_fault(
                    'dns cannot be configured if destination address translation is configured.',
                    'dns'))
            if 'service_translation' in self.values:
                faults.append(self.generate_fault(
                    'dns cannot be configured if service translation is configured.',
                    'dns'))

    def validate_unidirectional(self, faults):
        if 'unidirectional' in self.values:
            if self.values['source_translation']['nat_type'] != 'static':
                faults.append(self.generate_fault(
                    'unidirectional is only supported for static NAT.',
                    'unidirectional'))

    def __str__(self):
        return self.get_cli()

    @classmethod
    def get_cli_pattern(cls):
        if not cls.CLI_PATTERN:
            cls.CLI_PATTERN = re.compile(
                'nat \S+' +
                ' source (static|dynamic) (?:any|(\S+)) (?:any|(\S+))' + # Source address, groups 1,2,3
                '(?: destination static (\S+) (?:any|(\S+)))?' +         # Destination address, groups 4,5
                '(?: service (?:any|(\S+)) (\S+))?' +                    # Service, groups 6,7
                '( dns)?( unidirectional)?')                             # Options, groups 8, 9
        return cls.CLI_PATTERN

    @classmethod
    def parse_cli(cls, cli, order=None):
        m = cls.get_cli_pattern().match(cli)
        if m:
            result = {}
            if order:
                result['order'] = str(order)
            cls.parse_source_address(result, *m.group(1, 2, 3))
            cls.parse_destination_address(result, *m.group(4, 5))
            cls.parse_service(result, *m.group(6, 7))
            cls.parse_options(result, *m.group(8, 9))
            return result

    @staticmethod
    def parse_destination_address(result, mapped_object_name, real_object_name):
        if mapped_object_name:
            address = {'mapped_object_name': mapped_object_name}
            if real_object_name:
                address['real_object_name'] = real_object_name
            result['destination_translation'] = address

    @staticmethod
    def parse_options(result, dns, unidirectional):
        if dns:
            result['dns'] = None
        if unidirectional:
            result['unidirectional'] = None

    @staticmethod
    def parse_service(result, real_object_name, mapped_object_name):
        if mapped_object_name:
            service = {'mapped_object_name': mapped_object_name}
            if real_object_name:
                service['real_object_name'] = real_object_name
            result['service_translation'] = service

    @staticmethod
    def parse_source_address(result, nat_type, real_object_name, mapped_object_name):
        address = {'nat_type': nat_type}
        if real_object_name:
            address['real_object_name'] = real_object_name
        if mapped_object_name:
            address['mapped_object_name'] = mapped_object_name
        result['source_translation'] = address

class NATRuleDeployment(DMObject):
    'Options for deploying NAT rules'

    def __init__(self):
        DMObject.__init__(self, NATRuleDeployment.__name__)
        self.xlate_clis = []

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if (not self.has_ifc_delta_cfg() or
                self.delta_ifc_cfg_value['state'] == State.DESTROY):
            return

        # If translations are already cleared for ACLs, then not needed for NAT
        access_list_deployment = self.get_top().get_child('AccessListDeployment')
        if access_list_deployment and access_list_deployment.acl_changed:
            return

        values = normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if 'clear_translation' in values:
            no_asa_cfg_stack.extend(self.xlate_clis)

    def add_xlate(self, nat):
        nat_clii = nat.generate_clear_xlate()
        for clii in self.xlate_clis:
            # Don't add if it's a duplicate
            if nat_clii.command == clii.command:
                return
        self.xlate_clis.append(nat_clii)

class NATRuleList(DMList):
    'A list of NAT rules'

    def __init__(self):
        DMList.__init__(self, 'NATRule', NATRule, 'nat')
        self.diff_ifc_asa_nat_order = 1

    def diff_ifc_asa(self, cli):
        values = NATRule.parse_cli(cli, self.diff_ifc_asa_nat_order)
        if values:
            nat = NATRule(cli)
            nat.values = values
            self.diff_ifc_asa_nat_order += 1

            match_nat = self.find_nat(nat)
            if match_nat:
                match_nat.set_action(State.NOCHANGE)
            else:
                # Delete the NAT if it doesn't exist or is in a different order
                self.register_child(nat)
                nat.diff_ifc_asa(cli)

    def find_nat(self, nat):
        for match_nat in self.children.itervalues():
            if match_nat.values == nat.values:
                return match_nat

    def get_cli_prefix(self):
        return (
            'nat (' +
            self.get_interface_name('internal') +
            ',' +
            self.get_interface_name('external') +
            ')')

    def get_interface_name(self, connector_name):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(connector_name)
        return connector.get_nameif() if connector else ''

    def get_translator(self, cli):
        if isinstance(cli, basestring) and cli.startswith(self.get_cli_prefix()):
            return self

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Optimize the generated CLI by looking for NAT rules that have changed'

        # Split into old and new config
        old_config = []
        new_config = []
        for nat in self.children.itervalues():
            state = nat.get_state()
            if state == State.NOCHANGE:
                old_config.append(nat)
                new_config.append(nat)
            elif state == State.CREATE:
                new_config.append(nat)
            elif state == State.DESTROY:
                old_config.append(nat)

        # Sort the old and new config
        old_config.sort(key=lambda nat: int(nat.values['order']))
        new_config.sort(key=lambda nat: int(nat.values['order']))

        last_equal = -1
        for i, (old_nat, new_nat) in enumerate(zip(old_config, new_config)):
            if new_nat.equals_no_order(old_nat):
                last_equal = i
            else:
                break

        # Remove the old NAT rules which are different
        for nat in old_config[last_equal + 1:]:
            nat.generate_delete(no_asa_cfg_stack)

        # Add the new NAT rules which are different
        for nat in new_config[last_equal + 1:]:
            nat.generate_command(asa_cfg_list)

    def validate_configuration(self):
        faults = []
        self.validate_duplicates(faults)
        for child in self.children.values():
            self.report_fault(child.validate_configuration(), faults)
        return faults

    def validate_duplicates(self, faults):
        config = []
        for nat in self.children.itervalues():
            # Check the final configuration only
            if nat.get_state() in (State.NOCHANGE, State.CREATE):
                config.append(nat)
    
        if len(config) > 1:
            # Sort into order
            config.sort(key=lambda nat: int(nat.values['order']))
    
            # Check for duplicates
            for i, this_nat in enumerate(config[:-1]):
                for that_nat in config[i + 1:]:
                    if this_nat.equals_no_order(that_nat):
                        faults.append(that_nat.generate_fault(
                            'Duplicate NAT rule.'))
