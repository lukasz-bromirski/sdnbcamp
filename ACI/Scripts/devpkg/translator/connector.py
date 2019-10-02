'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''

import translator
from base.dmobject import DMObject
from translator.state_type import State, Type
from translator.base.dmlist import DMList
import asaio.cli_interaction as cli_interaction
import utils.util as util
from translator.structured_cli import StructuredCommand
from translator.sts import STSMap

class Connectors(DMList):
    def __init__(self, name, child_class, asa_key=''):
        DMList.__init__(self, name, child_class, asa_key)
        self.asa_key = 'interface'

    def is_my_cli(self, cli):
        'Also handle same-security-traffic'
        if isinstance(cli, str) and \
            cli == 'same-security-traffic permit inter-interface':
            Connector.is_same_security_traffic = True

        'Overwrite is_my_cli check, cli is a StructuredCommand in our case'
        if not isinstance(cli, StructuredCommand):
            return False # not handled by us

        'Must be an interface'
        if not cli.command.startswith('interface '):
            return False

        if not self.get_top().is_virtual() and not 'vni' in cli.command:
            'Must be a vlan interface'
            vlan = filter(lambda cmd: cmd.startswith('vlan'), cli.sub_commands)
            if not vlan:
                return False

        'Must bave instance name starting with external or internal'
        nameif = filter(lambda cmd: cmd.startswith('nameif'), cli.sub_commands)
        if not nameif:
            return False

        'Must handle by the same firewall instance'
        ancestor = self.get_ifc_delta_cfg_ancestor()
        self_fw_name = ancestor.get_firewall_name()

        name = nameif[0].split(' ')
        if '_external_' in name[1]:
            fw_name = name[1].split('_external_')[0]
            return self_fw_name == fw_name
        elif '_internal_' in name[1]:
            fw_name = name[1].split('_internal_')[0]
            return self_fw_name == fw_name
        else:
            return False

    @classmethod
    def get_connector_fw_name(cls, cli, is_virtual):
        'Overwrite is_my_cli check, cli is a StructuredCommand in our case'
        if not isinstance(cli, StructuredCommand):
            return None # not handled by us

        'Must be an interface'
        if not cli.command.startswith('interface '):
            return None

        if not is_virtual and not 'vni' in cli.command:
            'Must be a vlan interface'
            vlan = filter(lambda cmd: cmd.startswith('vlan'), cli.sub_commands)
            if not vlan:
                return None

        'Must bave instance name starting with external or internal'
        nameif = filter(lambda cmd: cmd.startswith('nameif'), cli.sub_commands)
        if not nameif:
            return None

        name = nameif[0].split(' ')
        if '_external_' in name[1]:
            fw_name = name[1].split('_external_')[0]
            return fw_name
        elif '_internal_' in name[1]:
            fw_name = name[1].split('_internal_')[0]
            return fw_name
        return None

class Connector(DMObject):
    '''
    A firewall service can contains two connectors of type external and internal.  A
    Connector in terms of ASA CLI is expressed by a VLAN interface.

    There are several ConnObj (VIF, VLAN, ENCAPASS) objects defined in the global
    configuration under Device Config.  These objects binds the vlan tag with the interface.

    When Connector generation CLI in ifc2asa() it retrieves the ConnObj that are
    associated with this Connector and invoke the ConnObj gen_ifc2asa().  gen_ifc2asa()
    is a function similar to DMObject.ifc2asa(), however, gen_ifc2asa() will be called
    by the Connector only.
    '''
    is_same_security_traffic = False  # static variable to track same-security-traffic is generated

    def is_my_cli(self, cli):
        'Do not process an ASA connector (no cli) object which was just created'
        if not hasattr(self, 'config'):
            return False
        is_virtual = self.get_top().is_virtual()
        if not is_virtual and not 'vni' in cli.command:
            'Must be a vlan interface'
            vlan = filter(lambda cmd: cmd.startswith('vlan'), cli.sub_commands)
            if not vlan:
                return False

        'Must have instance name presenting external or internal connector'
        nameif = filter(lambda cmd: cmd.startswith('nameif'), cli.sub_commands)
        instance = nameif[0].split(' ',1)[1]

        'Must have the same firewall and same nameif'
        if self.get_nameif() != None and self.get_nameif() != instance:
            return False

        self.get_connector_object()
        vif_obj = self.conn_obj.get('VIF')
        vlan_obj = self.conn_obj.get('VLAN')

        if 'vni' in cli.command:
            intf_command = 'interface vni%s' % (self.conn_obj.get('ENCAPASS').encap)
            'Check for segmnet id or vtep-nve?'
        elif is_virtual:
            intf_command = 'interface ' + vif_obj.value
        else:
            intf_command = 'interface %s.%s' % (vif_obj.value, vlan_obj.tag)

        'Check if interface command is the same with the cli'
        return cli.command == intf_command

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate the Connector configuration
        '''
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        self.config = util.normalize_param_dict(delta_ifc_cfg_value['value'])
        type, blank, self.instance_name  = self.delta_ifc_key
        if self.instance_name.startswith('external_'):
            self.conn_type = 'external'
        else:
            self.conn_type = 'internal'

    def get_nameif(self):
        '''
        Return the nameif with this format <firewall>_[external|internal]_<instance>
        '''
        ancestor = self.get_ifc_delta_cfg_ancestor()
        fw_name = ancestor.get_firewall_name()
        return fw_name + '_' + self.instance_name

    def get_intf_config_rel(self):
        if self.conn_type == 'external':
            return self.get_ancestor_by_class(translator.firewall.Firewall).get_child('ExIntfConfigRelFolder').get_child('ExIntfConfigRel')
        else:
            return self.get_ancestor_by_class(translator.firewall.Firewall).get_child('InIntfConfigRelFolder').get_child('InIntfConfigRel')

    def get_connector_object(self):
        '''
        Traverse to DeviceConfig and get the children ENCAPASS, VLAN, VIF, ip address and mask
        for this connector
        '''
        device_model = self.get_top()
        ass_list = device_model.get_child('ENCAPASS')
        vlan_list = device_model.get_child('VLAN')
        vif_list = device_model.get_child('VIF')
        interface_config_list = device_model.get_child('InterfaceConfig')
        intf_config_rel = self.get_intf_config_rel()

        self.conn_obj = {}
        self.conn_obj['ENCAPASS'] = ass_list.get_child(self.config.get('ENCAPREL'))
        if (self.conn_obj['ENCAPASS']):
            self.conn_obj['VLAN'] = vlan_list.get_child(self.conn_obj['ENCAPASS'].encap)
            self.conn_obj['VIF'] = vif_list.get_child(self.conn_obj['ENCAPASS'].vif)

        if hasattr(intf_config_rel, 'value'):
            self.conn_obj['InterfaceConfig'] = interface_config_list.get_child(intf_config_rel.value)

    def get_sts_key_and_type(self):
        fw_n_type = self.get_nameif()
        type_key = None
        if '_external_' in fw_n_type:
            fw_key = fw_n_type.split('_external_')[0]
            type_key = 'external'
        elif '_internal_' in fw_n_type:
            fw_key = fw_n_type.split('_internal_')[0]
            type_key = 'internal'
        sts_table = self.get_top().sts_table
        sts_map = sts_table.get(fw_key)
        if not sts_map:
            sts_table[fw_key] = STSMap()
        return fw_key, type_key

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''
        1. Enable the physical or port-channel interface
        Example:
            interface port-channel1
              no shutdown

        2. Create subinterface from physical or port-channel interface
            interface port-channel1.10
              vlan 10
              nameif external_Conn1
              security-level 50
              ip address 10.10.10.10 255.255.255.128

        There are three things that asa-dp has massaged on top of IFC configuration
        1. Mapped vlan tag as the port number of subinterface.
        2. Mapped Connector type and instance name as nameif.
           This may likely be changed but it is now a place holder.
        3. Set same-security-traffic once
        4. Added relationship to interface config for ip address/mask
        Note:  ASA will require interface to have nameif, ip address
        to work properly.
        '''
        if not self.has_ifc_delta_cfg():
            return

        if not Connector.is_same_security_traffic:
            'Generate same-security-traffic only once'
            self.generate_cli(asa_cfg_list, 'same-security-traffic permit inter-interface')
            Connector.is_same_security_traffic = True

        self.get_connector_object()
        vif_obj = self.conn_obj.get('VIF')
        vlan_obj = self.conn_obj.get('VLAN')
        interface_config_obj = self.conn_obj.get('InterfaceConfig')
        is_vxlan = (vlan_obj.type == '1')
        if is_vxlan:
            fw_key, type_key= self.get_sts_key_and_type()
        if vlan_obj.state == State.NOCHANGE:
            if is_vxlan:
                STSMap.set_sts_no_change(self, fw_key, type_key, vlan_obj.tag)
        if self.state == State.NOCHANGE:
            return
        'First, generate CLI for physical or virtual interface'
        if not is_vxlan:
            vif_obj.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list)
        'Second, generate CLI for VLAN interface'
        'user error if vlan is in MODIFY state'
        is_virtual = self.get_top().is_virtual()
        if is_vxlan:
            interface_command = 'interface vni%s' % (self.conn_obj.get('ENCAPASS').encap)
        elif is_virtual:
            interface_command = 'interface '+ vif_obj.value
        else:
            interface_command = 'interface %s.%s' % (vif_obj.value, vlan_obj.tag)
        self.response_parser = cli_interaction.ignore_info_response_parser
        if self.state == State.DESTROY:
            'Clear physical interface configurations'
            self.generate_cli(no_asa_cfg_stack, 'clear config ' + interface_command)
            if is_vxlan and not self.conn_obj.get('ENCAPASS').vif.startswith('DEL_') and \
                not self.conn_obj.get('ENCAPASS').vif.startswith('DEL_'):
                STSMap.set_sts_delete(self, fw_key, type_key, vlan_obj.tag)
        elif self.state in [State.CREATE, State.MODIFY]:
            self.mode_command = interface_command
            if is_vxlan:
                STSMap.set_sts_add(self, fw_key, type_key, vlan_obj.tag)
                self.generate_cli(asa_cfg_list, 'vtep-nve 1')
                self.generate_cli(asa_cfg_list, 'tag-switching')
            if not is_virtual :
                vlan_obj.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, interface_command)
            'For now use Connector type and instance name for nameif'
            self.generate_cli(asa_cfg_list, 'nameif ' + self.get_nameif())
            if interface_config_obj:
                interface_config_obj.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, interface_command)

    def get_vlan_interface(self):
        self.get_connector_object()
        vif_obj = self.conn_obj.get('VIF')
        vlan_obj = self.conn_obj.get('VLAN')
        if self.get_top().is_virtual():
            return vif_obj.value
        return '%s.%s' % (vif_obj.value, vlan_obj.tag)

    def diff_ifc_asa(self, cli):
        '''
        Check if any state needs to be updated.  If it has no ifc delta config,
        we should remove this CLI from ASA.
        '''
        if not self.has_ifc_delta_cfg():
            self.gen_destroy_conn_delta_ifc_value(cli)
            return

        self.updateState(cli)

    def gen_destroy_conn_delta_ifc_value(self, structuredcli):
        cli = structuredcli.command
        nameif_cli = filter(lambda cmd: cmd.startswith('nameif'), structuredcli.sub_commands)
        self.instance_name = nameif_cli[0].split(' ',1)[1]
        if '_external_' in self.instance_name:
            fw, instance = self.instance_name.split('_external_')
            self.conn_type = 'external'
        elif '_internal_' in self.instance_name:
            fw, instance = self.instance_name.split('_internal_')
            self.conn_type = 'internal'

        self.instance_name = self.conn_type + '_' + instance

        if self.get_top().is_virtual() or 'vni' in cli:
            intf = cli.split(' ')[1]
            label = intf
            vlan = ''
            if 'vni' in cli:
                segment_cli = filter(lambda cmd: cmd.startswith('segment-id'), structuredcli.sub_commands)
                vlan = segment_cli[0].split('segment-id')[1]
                encap = intf.split('vni')[1]
            else: 
                encap = 'DEL_VLAN-' + label
        else:
            'Split CLI into interface and vlan'
            intf, vlan = cli.split(' ')[1].split('.')
            label = intf + '_' + vlan
            encap = 'DEL_VLAN-' + label

        'Create DEL_ instance names for new conn_obj config'
        assoc = 'DEL_ASSOC_' + label
        vif = 'DEL_VIF' + label

        'Create key and values'
        encapass_key = (Type.ENCAPASS, 'ENCAPASS', assoc)
        encapass_config = {'state': State.DESTROY, 'encap':encap, 'vif':vif}

        is_vxlan = '1' if 'vni'in label else '0'
        encap_key = (Type.ENCAP, 'VLAN', encap)
        encap_config = {'state': State.DESTROY, 'tag':vlan, 'type':is_vxlan}
        "Add the key-value config to its container's delta_ifc_cfg_value"
        ancestor = self.get_top()
        if not 'vni' in cli:
            vif_key = (Type.VIF, 'VIF', vif)
            vif_config = {'state': State.DESTROY, 'cifs':{fw:intf}}
            ancestor.delta_ifc_cfg_value['value'][vif_key] = vif_config
        ancestor.delta_ifc_cfg_value['value'][encap_key] = encap_config
        ancestor.delta_ifc_cfg_value['value'][encapass_key] = encapass_config

        key = (Type.CONN, self.conn_type, instance)
        config = {'state': State.DESTROY, 'value': {
            (Type.ENCAPREL, '', ''): {'state':State.DESTROY, 'target':assoc}
        }}

        'Get or create firewall ancestor and append the connector content'
        firewalls = self.get_ancestor_by_class(translator.firewall.Firewalls)
        firewall = firewalls.get_firewall(fw)
        firewall.delta_ifc_cfg_value['value'][key] = config
        firewalls.parent.delta_ifc_cfg_value['value'][firewall.delta_ifc_key] = firewall.delta_ifc_cfg_value

    def build_cli_dict(self, cli):
        cli_dict = {}
        for c in cli.sub_commands:
            keys = c.split()

            if 'ipv6 nd prefix' in c:
                cli_dict[keys[3]] = c
            elif 'ipv6 nd' in c or 'ipv6 address' in c:
                if 'link-local' in c:
                    cli_dict['link-local'] = c
                else:
                    cli_dict[keys[2]] = c
            elif 'ipv6 enable' in c:
                cli_dict['enable'] = c
            elif 'ipv6 enforce-eui64' in c:
                cli_dict['enforce-eui64'] = c
            elif 'secondary' in c:
                cli_dict[keys[1]] = c
            elif 'originate' in c:
                cli_dict[keys[1]] = c
            else:
                key = c.split(' ', 1)[0]
                cli_dict[key] = c
        return cli_dict

    def updateState(self, cli):
        '''
        Update the state if necessary
        '''
        self.get_connector_object()
        vif_obj = self.conn_obj.get('VIF')
        vlan_obj = self.conn_obj.get('VLAN')
        interface_config_obj = self.conn_obj.get('InterfaceConfig')
        cli_dict = self.build_cli_dict(cli)
        accum_state = []
        if vlan_obj.type == '0':
            '1 - vif: interface <label.port>'
            accum_state.append(vif_obj.gen_diff_ifc_asa(cli.command))

        if vlan_obj.type == '1':
            accum_state.append(vlan_obj.gen_diff_ifc_asa(cli_dict['segment-id']))
        elif not self.get_top().is_virtual():
            '2 - vlan <num>'
            accum_state.append(vlan_obj.gen_diff_ifc_asa(cli_dict['vlan']))

        '3 - InterfaceConfig:'
        ' - ip address <ip> <mask>'
        ' - security_level <level>'
        ' - ipv6 address x:x:x:x::/previx [eui-64]'
        ' - ipv6 address autoconfig'
        ' - ipv6 enable'
        ' - ipv6 nd prefix x:x:x:x::/prefix [n1 n2] [at d1 d2] [off-link] [no-autoconfig] [no-advertise]'
        ' - ipv6 nd dad attempts < 0-600>'
        ' - ipv6 nd ns-interval <1000-36000000'
        ' - ipv6 nd reachable-time <0-36000000'
        ' - ipv6 nd ra-interval <500-1800000>'
        ' - ipv6 nd ra-lifetime <0-9000>'
        ' - segment-id <1-16million> secondary'
        ' - segment-id <1-16million> originate'
        if interface_config_obj:
            accum_state.append(interface_config_obj.gen_diff_ifc_asa(cli_dict))

        if State.MODIFY in accum_state:
            self.delta_ifc_cfg_value['state'] = State.MODIFY
        elif State.NOCHANGE in accum_state:
            self.delta_ifc_cfg_value['state'] = State.NOCHANGE

class ConnObj(DMObject):
    '''
    This is a base class for all connector objects that are defined under
    Device Config (VIF, VLAN, ENCAPASS, InterfaceConfig).  It overwrite the populate_model()
    and ifc2asa() method. The Connector will handle the generation of CLI
    instead of handling it in these objects.

    Note:  ConnObj are not specified in device specification, they are
    generated by the IFC, except InterfaceConfig which is a relationship binding
    interface to ip address/mask.
    '''
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        self.response_parser = cli_interaction.ignore_info_response_parser

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Handled by Connector'
        pass

class Vifs(DMList):
    def __init__(self):
        DMList.__init__(self, 'VIF', Vif, 'interface')
        self.asa_key = 'interface'

    def is_my_cli(self, cli):
        'Overwrite is_my_cli check, cli is a StructuredCommand in our case'
        if not isinstance(cli, StructuredCommand):
            return False # not handled by us

        'Must be an interface'
        if not cli.command.startswith('interface '):
            return False

        if 'vni' in cli.command or 'BVI' in cli.command or 'TVI' in cli.command:
            return False

        'Must bave instance name starting with external or internal'
        nameif = filter(lambda cmd: cmd.startswith('nameif'), cli.sub_commands)
        if not nameif:
            return False

        'Must not have external nor internal'
        nameif = nameif[0].split(' ',1)[1]
        if '_internal_' in nameif or '_external_' in nameif:
            return False

        return True

class Vif(ConnObj):
    '''
    (1) In ASA platform, Virtual interface or physical interface that vlan interface will spawn from
    (2) In vASA platform, only generate physical interface
    (3) In ASA platform and in vxlan type, generate base interface where nve is referenced as source-interface
    '''
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        super(Vif, self).populate_model(delta_ifc_key, delta_ifc_cfg_value)
        self.value = delta_ifc_cfg_value['cifs'].iteritems().next()[1]
        self.value = self.value.replace('_', '/')

    def isVXLAN(self):
        '''
        Check wherether this is a vxlan by checking whether is is referenced
        by a vxlan interface.
        '''
        device_model = self.get_top()
        ass_list = device_model.get_child('ENCAPASS')
        vlan_list = device_model.get_child('VLAN')
        children = ass_list.children
        for ass_obj in children.values():
            if ass_obj.vif == self.ifc_key:
                vlan_obj = vlan_list.get_child(ass_obj.encap)
                return True if vlan_obj and vlan_obj.type == '1' else False
        return False

    def is_my_cli(self, cli):
        if not self.isVXLAN():
            return
        return cli.command == 'interface ' + self.value

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'This method is called when interface is VXLAN, it will create the base interface'
        is_vxlan = self.isVXLAN()
        if not is_vxlan:
            return

        if not self.has_ifc_delta_cfg():
            return

        if self.state == State.NOCHANGE:
            return

        self.response_parser = cli_interaction.ignore_info_response_parser
        cli = 'interface ' + self.value

        if self.state == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack, 'clear config ' + cli)
            return
        if self.state in [State.CREATE, State.MODIFY]:
            self.mode_command = cli
            self.generate_cli(asa_cfg_list, 'nameif ' + self.ifc_key)
            self.generate_cli(asa_cfg_list, 'no shutdown')

        interface_config_list = self.get_top().get_child('InterfaceConfig')
        intf_config_obj = interface_config_list.get_child(self.ifc_key)
        if intf_config_obj:
            intf_config_obj.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, cli)

    def build_cli_dict(self, cli):
        cli_dict = {}
        for c in cli.sub_commands:
            keys = c.split()
            if 'ipv6 nd prefix' in c:
                cli_dict[keys[3]] = c
            elif 'ipv6 nd' in c or 'ipv6 address' in c:
                if 'link-local' in c:
                    cli_dict['link-local'] = c
                else:
                    cli_dict[keys[2]] = c
            elif 'ipv6 enable' in c:
                cli_dict['enable'] = c
            elif 'ipv6 enforce-eui64' in c:
                cli_dict['enforce-eui64'] = c
            else:
                key = c.split(' ', 1)[0]
                cli_dict[key] = c
        return cli_dict

    def diff_ifc_asa(self, cli):
        if not self.isVXLAN():
            return
        if not self.has_ifc_delta_cfg():
            return
        interface_config_list = self.get_top().get_child('InterfaceConfig')
        intf_config_obj = interface_config_list.get_child(self.ifc_key)
        cli_dict = self.build_cli_dict(cli)

        accum_state = []
        if intf_config_obj:
            accum_state.append(intf_config_obj.gen_diff_ifc_asa(cli_dict))

        if State.MODIFY in accum_state:
            self.delta_ifc_cfg_value['state'] = State.MODIFY
        elif State.NOCHANGE in accum_state:
            self.delta_ifc_cfg_value['state'] = State.NOCHANGE

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''
        Generate ASA configuration from IFC configuration delta.
        May need to created and/or enable this interface.  This is not the vlan interface,
        it is the interface where it is sub interface from.
        '''
        if not self.has_ifc_delta_cfg():
            return

        if self.state == State.NOCHANGE:
            return

        self.response_parser = cli_interaction.ignore_info_response_parser
        cli = 'interface ' + self.value
        self.response_parser = cli_interaction.ignore_info_response_parser
        if self.state in [State.CREATE, State.MODIFY]:
            self.mode_command = cli
            self.generate_cli(asa_cfg_list, 'no shutdown')

    def gen_diff_ifc_asa(self, interface):
        '''
        Check if any state changes needed.
        '''
        if self.get_top().is_virtual():
            intf_command = 'interface %s' % (self.value)
        else:
            intf_command = 'interface %s.' % (self.value)
        if not interface.startswith(intf_command):
            self.delta_ifc_cfg_value['state'] = State.CREATE
        else:
            self.delta_ifc_cfg_value['state'] = State.NOCHANGE
        return self.delta_ifc_cfg_value['state']

class Vlan(ConnObj):
    '''
    Describe the VLAN tag
    '''
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        super(Vlan, self).populate_model(delta_ifc_key, delta_ifc_cfg_value)
        self.type = str(delta_ifc_cfg_value.get('type'))
        '''
        hardcode to avoid triggering vxlan code in brownfield because an APIC bug
        which is still generating 1 instead of 0
        '''
        self.type = '0'
        self.tag = delta_ifc_cfg_value.get('tag')

    def gen_vlan_cli(self, no_asa_cfg_stack, asa_cfg_list, mode):
        '''
        MODIFY state is not supported, modify a VLAN will modify the subinterface port
        number which will create a different interface instead of modifying the current
        specified port-channel.
        '''
        if self.state != State.DESTROY:
            self.mode_command = mode
            self.generate_cli(asa_cfg_list, 'vlan %s' %(self.tag))

    def gen_vxlan_cli(self, no_asa_cfg_stack, asa_cfg_list, mode):
        '''
        MODIFY state is supported for vxln changing the segment-id
        '''
        if self.state == State.NOCHANGE:
            return
        if self.state in [State.CREATE, State.MODIFY]:
            self.mode_command = mode
            self.generate_cli(asa_cfg_list, 'segment-id %s' %(self.tag))

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, mode):
        '''
        Generate vlan or vxlan cli depends on the vlan type
        '''
        if not self.has_ifc_delta_cfg():
            return

        if self.type == '0':
            self.gen_vlan_cli(no_asa_cfg_stack, asa_cfg_list, mode)
        else:
            self.gen_vxlan_cli(no_asa_cfg_stack, asa_cfg_list, mode)

    def gen_diff_ifc_asa(self, vlan):
        '''
        Check if any state changes needed
        '''
        vlan = vlan.split(' ', 1)[1]

        if vlan != str(self.tag):
            self.delta_ifc_cfg_value['state'] = State.MODIFY
        else:
            self.delta_ifc_cfg_value['state'] =  State.NOCHANGE
        return self.delta_ifc_cfg_value['state']

class EncapAss(ConnObj):
    '''
    Present the association of VLAN and VIF
    '''
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        super(EncapAss, self).populate_model(delta_ifc_key, delta_ifc_cfg_value)
        self.vif = delta_ifc_cfg_value['vif']
        self.encap = delta_ifc_cfg_value['encap']

class IntfConfigRel(DMObject):
    '''
    Populate interfaceConfig for external or internal connector
    '''
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        'Will deprecate check for target once the target is replaced with value in the initialization'
        if 'target' in delta_ifc_cfg_value:
            self.value = delta_ifc_cfg_value['target']
        else:
            self.value = delta_ifc_cfg_value['value']

class ExIntfConfigRel(IntfConfigRel):
    def __init__(self):
        DMObject.__init__(self, ExIntfConfigRel.__name__)

class InIntfConfigRel(IntfConfigRel):
    def __init__(self):
        DMObject.__init__(self, InIntfConfigRel.__name__)

class ExIntfConfigRelFolder(DMObject):
    'A list of additional interface parameters for external Connectors'

    def __init__(self):
        DMObject.__init__(self, ExIntfConfigRelFolder.__name__)
        self.register_child(ExIntfConfigRel())

class InIntfConfigRelFolder(DMObject):
    'A list of additional interface parameters for internal Connectors'

    def __init__(self):
        DMObject.__init__(self, InIntfConfigRelFolder.__name__)
        self.register_child(InIntfConfigRel())

class IPv6EnforceEUI64(DMObject):
    'Model after  "ipv6 enforce-eui64 <nameif>'
    def __init__(self, type):
        DMObject.__init__(self, ifc_key = 'ipv6_enforce_eui64')
        self.conn_type = type

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        '''
        Populate model
        '''
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        self.response_parser = cli_interaction.ignore_info_response_parser

    def get_enforce_eui64_cli(self):
        'Override the default implementation to take care / delimiter'
        assert self.has_ifc_delta_cfg()
        return 'ipv6 enforce-eui64 ' + self.get_nameif()

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        if not self.has_ifc_delta_cfg():
            return
        state = self.state
        if state == State.NOCHANGE:
            return

        if state == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack, 'no ' + self.get_enforce_eui64_cli())
        elif state in [State.CREATE, State.MODIFY]:
            self.response_parser = cli_interaction.ignore_info_response_parser
            self.generate_cli(asa_cfg_list, self.get_enforce_eui64_cli())

    def get_nameif(self):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(self.conn_type)
        if connector:
            nameif = connector.get_nameif()
        return nameif

    def is_my_cli(self, cli):
        '''
        Check if this cli belogs to ipv6 enforce-eui64 and matches the nameif.
        '''
        if not isinstance(cli, str):
            return False
        if cli.startswith('ipv6 enforce-eui64'):
            nameif = cli.split()[2]
            if nameif == self.get_nameif():
                return True
        return False

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            self.delta_ifc_key = (Type.PARAM, 'ipv6_enforce_eui64', self.get_cli())
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': 'enable'}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        self.update_state(cli)

    def update_state(self, cli):
        if self.get_enforce_eui64_cli() == cli:
            self.delta_ifc_cfg_value['state'] = State.NOCHANGE
        else:
            self.delta_ifc_cfg_value['state'] = State.MODIFY

class InIPv6EnforceEUI64(DMObject):
    def __init__(self):
        DMObject.__init__(self, InIPv6EnforceEUI64.__name__)
        self.register_child(IPv6EnforceEUI64('internal'))

class ExIPv6EnforceEUI64(DMObject):
    def __init__(self):
        DMObject.__init__(self, ExIPv6EnforceEUI64.__name__)
        self.register_child(IPv6EnforceEUI64('external'))
