'''
Created on Dec 1, 2013

@author: linlilia

Copyright (c) 2013 by Cisco Systems

This module is for the configuration of DNS server.

How to configure the DNS server:
Step 1: enable the ASA to send DNS requests to a DNS server to perform a name lookup for supported commands.
     CLI: dns domain-lookup <interface_name>

     The value of <interface_name> can be retrieved from 'utitlity' interface in device_specification.
     So the dns domain-lookup specification is hidden from device_specification.

Step 2: Specifies the DNS server group that the ASA uses for outgoing requests.
(Other DNS server groups are configured for VPN tunnel groups, which are not supported here)
    CLI: dns server-group DefaultDNS

Step 3: Specifies one or more DNS servers under the name-server submode. You can enter up to six IP addresses. The ASA tries each DNS server in order until it receives a response.
    CLI: name-server <ip_address>

Step 4: Specifies one domain name.
    CLI: domain-name <host>

Optional Step(not supported now):
    Specify dns settings, such as number of retries, timeout values, the timer time in minutes and poller time for the DNS server.
    CLIs:
       timeout <seconds>
       retries <times>
       expire-entry-timer minutes <minutes>
       poll-timer minutes <minutes>
     Note: These are hidden now since they are optional and the default settings are sufficient to be used.
     We can use SimpleType class to implement these settings in the future.

Example:
      dns domain-lookup management
      dns server-group DefaultDNS
        domain-name cisco.com
        name-server 171.70.168.183
        name-server 173.36.131.10
        name-server 173.37.87.157
'''
from translator.base.dmlist import DMList
from translator.base.dmobject import DMObject
from base.simpletype import SimpleType
from base.compositetype import CompositeType
from translator.state_type import Type, State

class DNS(DMObject):
    '''
    Container of DNS
    '''
    def __init__(self):
        DMObject.__init__(self, DNS.__name__)
        self.register_child(DNSDomainLookup())
        self.register_child(DNSServer())

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        'Override the default implementation because the IFC model does not directly map to self.children of DNSServer'
        DMObject.populate_model(self, delta_ifc_key, delta_ifc_cfg_value)

        'Let DNSServer share the configuration with this translator'
        dns_server = self.children.values()[1]
        dns_server.populate_model(delta_ifc_key, delta_ifc_cfg_value)

class DNSServer(CompositeType):
    '''
    Model for the DNS server group configuration:
        dns server-group DefaultDNS
          name-server <ip-address>
    '''
    def __init__(self):
        CompositeType.__init__(self, ifc_key = DNSServer.__name__, asa_key = 'dns server-group DefaultDNS')
        self.register_child(SimpleType("domain_name", "domain-name"))
        self.register_child(DMList('name_server', DNSNameServer, 'name-server'))

    def get_cli(self):
        return self.asa_key

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        '''
        Override the default implementation to handle destroy case because
          'dns server-group DefaultDNS'cannot be removed, but the children CLIs should be removed.
        The destroy part has be to skipped from CompositeType.ifc2asa because it only generate no cli for self.

        For example, CLIs will be generated like this when the DNS folder's state is DESTROY:
                dns server-group DefaultDNS
                  no name-server 173.36.131.10
                  no name-server 171.70.168.183
                  no domain-name cisco.com
        '''
        if not self.has_ifc_delta_cfg():
            return

        'Generate CLIs from the children even for destroy state'
        child_mode_command = self.get_child_mode_command()
        for child in self.children.values():
            child.mode_command = child_mode_command
            if isinstance(child, DMList):
                for c in child.children.values():
                    c.mode_command = self.get_cli()
            child.ifc2asa(no_asa_cfg_stack, asa_cfg_list)

class DNSNameServer(SimpleType):
    '''
    Model for CLI 'name-server <ip-address>'
    up to 6 IP addresses
    '''
    def __init__(self, name):
        SimpleType.__init__(self, name, asa_gen_template='name-server %s')

    def create_asa_key(self):
        return self.get_cli()

class DNSDomainLookup(SimpleType):
    '''
    Model for CLIs:
       domain-lookup <interface_name>

    Caveats:
      1. The only thing it does is to enable the domain look-up on the utility interface.
      2. No destroy is handled
      3. ToDo: Need to wait IFC to provide the way how to get the interface info from 'utility' interface
         Same issue on NTP, Logging and cluster(use mgmt interface)
         Defect to track: CSCum19136
    '''
    def __init__(self):
        '''
        Constructor
        '''
        SimpleType.__init__(self, "domain_lookup", 'dns domain-lookup')

    def get_action(self):
        '''
        @return the ancestor's state for this object
        '''
        ancestor = self.get_ifc_delta_cfg_ancestor()
        return ancestor.delta_ifc_cfg_value['state']

    def get_cli(self):
        'Override default to generate cli with utility interface name'
        nameif = self.get_top().get_utility_nameif()
        if nameif:
            return self.asa_key + ' ' + nameif
        else:
            return ''

    def ifc2asa(self, no_asa_cfg_stack,  asa_cfg_list):
        '''
        Override the default implementation to generate CLI with utility interface name
        '''
        # no need to generate CLI with utility interface name if no change after auditing
        if self.has_ifc_delta_cfg() and self.delta_ifc_cfg_value['state'] == State.NOCHANGE:
            return

        action = self.get_action()
        if action == State.NOCHANGE:
            return

        new_cli = self.get_cli()
        if new_cli:  # if there is valid utility interface
            if action in (State.CREATE, State.MODIFY):
                self.generate_cli(asa_cfg_list, new_cli)
            elif action == State.DESTROY and self.is_removable:
                self.generate_cli(no_asa_cfg_stack, 'no ' + new_cli)
