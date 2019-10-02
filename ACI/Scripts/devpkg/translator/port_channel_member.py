'''
Copyright (c) 2013 by Cisco Systems, Inc.

@author: emilymw
'''
import translator
from base.dmlist import DMList
from base.dmobject import DMObject
from translator.state_type import State, Type
from translator.structured_cli import StructuredCommand
import asaio.cli_interaction as cli_interaction
from utils.util import normalize_interface_name

class PortChannelMembers(DMList):
    'Container of PortChannelMember'
    def __init__(self):
        DMList.__init__(self, name='PortChannelMember', asa_key = 'interface', child_class=PortChannelMember)

    def is_my_cli(self, cli):
        'Must be an interface with channel-group subcommand'
        if not isinstance(cli, StructuredCommand):
            return False
        if not cli.command.startswith('interface '):
            return False
        channel_cli = filter(lambda cmd: cmd.startswith('channel-group'), cli.sub_commands)
        if len(channel_cli) == 0:
            return False
        return True

class PortChannelMember(DMObject):
    'Model interface with channel-group subcommand'
    def __init__(self, name):
        DMObject.__init__(self, name)
        self.register_child(ChannelGroup())
        self.register_child(InterfaceObject())
        self.response_parser = cli_interaction.ignore_info_response_parser
        
    def set_action(self, state):
        self.delta_ifc_cfg_value['state'] = state

    def get_channel_group_cli(self):
        child = self.get_child('port_channel_id')
        return child.get_channel_group_cli()

    def is_my_cli(self, cli):
        '''
        Must have the same interface mode command
        '''
        intf = self.get_child('interface')
        if intf:
            return intf.get_interface_cli() == cli.command
        return False

    def get_translator(self, cli):
        if self.is_my_cli(cli):
            return self
        return None

    def diff_ifc_asa(self, cli):
        'Diff the channel group or create PortChannelGroupMember'
        if not self.has_ifc_delta_cfg():
            channel_cli = filter(lambda cmd: cmd.startswith('channel-group'), cli.sub_commands)
            channel_group = channel_cli[0].split(' ')[1]

            self.delta_ifc_key = (Type.FOLDER, 'PortChannelMember', 'pc' + channel_group + '_' + cli.command)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value': {}}
            ancestor = self.get_ancestor_by_class(translator.devicemodel.DeviceModel)
            if not self.delta_ifc_key in ancestor.delta_ifc_cfg_value['value']:
                ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value

            for child in self.children.values():
                child.diff_ifc_asa(cli)
            return
        if self.is_the_same_cli(cli):
            self.set_action(State.NOCHANGE)
        else:
            self.set_action(State.MODIFY)

    def is_the_same_cli(self, cli):
        '@return if the given CLI is the same as the one represented by me'
        return self.get_channel_group_cli() == \
            filter(lambda cmd: cmd.startswith('channel-group'), cli.sub_commands)[0]

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Generate CLI based on state'
        if not self.has_ifc_delta_cfg():
            return

        if self.delta_ifc_cfg_value['state'] == State.NOCHANGE:
            return

        channel_group = self.get_child('port_channel_id')
        interface = self.get_child('interface')
        interface.gen_ifc2asa(no_asa_cfg_stack, asa_cfg_list, channel_group)

class InterfaceObject(DMObject):
    def __init__(self):
        DMObject.__init__(self, ifc_key = 'interface')

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        'Populate model'
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']
        self.delta_ifc_cfg_value['value'] = self.delta_ifc_cfg_value['value'].replace('_', '/')
        
    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''
        Handled by PortChannelMember which will invoke self.gen_ifc2asa() because
        physical interface cannot be deleted
        '''
        pass

    def get_interface_cli(self):
        'Return the cli of the interface command'
        return 'interface ' + normalize_interface_name(self.delta_ifc_cfg_value['value'])

    def diff_ifc_asa(self, cli):
        if not self.has_ifc_delta_cfg():
            intf_cli = cli.command.split(' ')
            intf = intf_cli[1]

            self.delta_ifc_key = (Type.PARAM, 'interface', intf)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value':intf}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return

    def gen_ifc2asa(self, no_asa_cfg_stack, asa_cfg_list, channel_group):
        'Generate the cli invoked from the container class PortChannelMember'
        if not self.has_ifc_delta_cfg():
            return

        if self.state == State.NOCHANGE and channel_group.state == State.NOCHANGE:
            return

        interface_cli = self.get_interface_cli()
        channel_group_cli = channel_group.get_channel_group_cli()
        self.mode_command = interface_cli

        if self.state == State.DESTROY:
            self.generate_cli(no_asa_cfg_stack, channel_group_cli)
        elif self.state in [State.CREATE, State.MODIFY] or channel_group.state in [State.CREATE, State.MODIFY]:
            self.response_parser = cli_interaction.ignore_info_response_parser
            if self.state == State.CREATE:
                self.generate_cli(asa_cfg_list, "no shutdown")
            self.generate_cli(asa_cfg_list, channel_group_cli)               

class ChannelGroup(DMObject):
    'ChannelGroup class model the channel-group cli'
    def __init__(self):
        DMObject.__init__(self, ifc_key = 'port_channel_id')

    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        self.delta_ifc_key = delta_ifc_key
        self.delta_ifc_cfg_value = delta_ifc_cfg_value
        self.state = delta_ifc_cfg_value['state']

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Handled by InterfaceObject'
        pass

    def diff_ifc_asa(self, cli):
        'Compare cli and update action state'
        channel_cli = filter(lambda cmd: cmd.startswith('channel-group'), cli.sub_commands)
        channel_group = channel_cli[0].split(' ')[1]

        if not self.has_ifc_delta_cfg():       
            self.delta_ifc_key = (Type.PARAM, 'port_channel_id', cli.command + '_' + channel_group)
            self.delta_ifc_cfg_value = {'state': State.DESTROY, 'value':channel_group}
            ancestor = self.get_ifc_delta_cfg_ancestor()
            ancestor.delta_ifc_cfg_value['value'][self.delta_ifc_key] =  self.delta_ifc_cfg_value
            return
        if channel_cli == self.get_channel_group_cli():
            self.delta_ifc_cfg_value['state'] = State.NOCHANGE
        else:
            self.delta_ifc_cfg_value['state'] = State.MODIFY

    def get_channel_group_cli(self):
        'Return cli of a channel-group'
        cli = 'channel-group %s mode active' % self.delta_ifc_cfg_value['value']
        if self.state == State.DESTROY:
            return 'no ' + cli
        return cli
