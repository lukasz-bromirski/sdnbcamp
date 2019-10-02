'''
Created on Sep 30, 2013

@author: tsnguyen
'''
from translator.base.dmobject import DMObject
from translator.state_type import State, Type
from translator.base.simpletype import SimpleType
from translator.base.dmlist import DMList
import utils.util as util
from asaio.cli_interaction import CLIInteraction
 

class NetFlowObjects(DMObject):
    ''' Class for all NetFlow global objects such as collectors, templates'''
    collectors = {}
    
    def __init__(self):
        ''' Initialize '''
        DMObject.__init__(self, 'NetFlowObjects')
        self.register_child(TemplateAndCollectors())
                
        
    def query_collectors(self):
        ''' Get collector list '''
        
        if not self.get_top().get_device():
            return
        NetFlowObjects.collectors = {}
        query_cmd = 'show run flow-export | grep destination'
        res = self.query_asa(query_cmd)    
        
        if not res or not len(res):
            return
        
        lines = res.split('\n')
        for cli in lines:
            values = util.normalize_param_dict(NetFlowCollectors.parse_destination(cli))
            key = NetFlowCollectors.get_collector_info(values)
            NetFlowObjects.collectors[key] = 'enable'
        
class NetFlowSubCommands(DMObject):
    ''' Class for all NetFlow service policy '''
   
    
    def __init__(self):
        ''' Initialize '''
        DMObject.__init__(self, ifc_key = 'NetFlowSettings', asa_key='flow-export')
        self.mode_command = None
        self.register_child(ExportEventType('ExportAllEvent', 'flow-export event-type all destination'))
        self.register_child(ExportEventType('ExportCreationEvent', 'flow-export event-type flow-create destination'))
        self.register_child(ExportEventType('ExportDenyEvent', 'flow-export event-type flow-denied destination'))
        self.myconfig = None
    
    
    def diff_ifc_asa(self, cli):
       
        translator = self.get_child_translator(cli)
        if translator:
            translator.diff_ifc_asa(cli)
        

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        '''
        Override the default implementation for translating IFC config to ASA config
        '''
        
        if self.has_ifc_delta_cfg():
            self.myconfig = self.delta_ifc_cfg_value
        if not self.myconfig:
            return
        action = self.myconfig['state']
        if action == State.NOCHANGE:
            return
        settings = self.myconfig['value']
        for (type, key, inst), value in settings.iteritems():
            if key in [ 'ExportAllEvent', 'ExportCreationEvent', 'ExportDenyEvent']:
                child = self.get_child(key)
                child.action = value['state']
                child.mode_command = self.mode_command if hasattr(self, 'mode_command') and self.mode_command else None
                child.config = util.normalize_param_dict(value['value'])
                child.ifc2asa(no_asa_cfg_stack, asa_cfg_list)
                
        
    def get_child_translator(self, cli):
        if cli.find('event-type all') >= 0:
            return self.get_child('ExportAllEvent')
        elif cli.find('event-type flow-creation') >= 0:
            return self.get_child('ExportCreationEvent')
        elif cli.find('event-type flow-denied') >= 0:
            return self.get_child('ExportDenyEvent')
        return None
        

class ExportEventType(SimpleType):
    ''' Class for all event export '''
    FLOW_EXPORT_ALL_EVENT_DESTINATION = 'flow-export event-type all destination'
    FLOW_EXPORT_CREATION_EVENT_DESTINATION = 'flow-export event-type flow-creation destination'
    FLOW_EXPORT_DENY_EVENT_DESTINATION = 'flow-export event-type flow-denied destination'
    
    
    def __init__(self, ifc_key='ExportAllEvent', asa_key='flow-export event-type all'):
        self.action = None
        self.destination = None
        self.config = None
        self.status = 'enable'
        template = None
        if ifc_key == 'ExportAllEvent':
            template = self.FLOW_EXPORT_ALL_EVENT_DESTINATION + ' %(event_destination)s'
        elif ifc_key == 'ExportCreationlEvent':
            template = self.FLOW_EXPORT_CREATION_EVENT_DESTINATION + ' %(event_destination)s'
        elif ifc_key == 'ExportDenyEvent':
            template = self.FLOW_EXPORT_DENY_EVENT_DESTINATION + ' %(event_destination)s'
        
        SimpleType.__init__(self, ifc_key, asa_key, asa_gen_template = template, response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        

    
    def is_the_same_cli(self, cli):
        'Override default implementation to compare individual data'
        
        find_id = cli.find(self.get_asa_key())
        if find_id >= 0:
            destination = cli[find_id + len(self.get_asa_key()) + 1:]
            if find_id > 0:
                status = 'disable'
            else:
                status = 'enable'
            return destination == self.destination and self.status == status
             
        else:
            return False
        

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        self.destination = self.config['event_destination']
        self.status = self.config.get('status', 'enable')
        if self.action == State.CREATE or self.action == State.MODIFY:
            self.ifc2asa_create_modify(no_asa_cfg_stack, asa_cfg_list)
        elif self.action == State.DESTROY:
            asa_cfg_list.append(self.generate_single_cli(False)) 
                
    def ifc2asa_create_modify(self, no_asa_cfg_stack, asa_cfg_list):
        ''' IFC to ASA create '''
        if not self.destination:
            return
        
        if self.status == 'enable':
            asa_cfg_list.append(self.generate_single_cli(True))
        else: 
            asa_cfg_list.append(self.generate_single_cli(False))
        
  
    def generate_single_cli(self, enabled):
        ''' Generate a CLI '''
        
        if enabled:
            return CLIInteraction(self.get_asa_key() + ' ' + self.destination, mode_command = self.mode_command, response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        else:
            return CLIInteraction('no ' + self.get_asa_key() + ' ' + self.destination, mode_command = self.mode_command, response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        
    def parse_single_parameter_cli(self, cli):
        ''' Parse CLI '''
        result = {}
        find_id = cli.find(self.get_asa_key())
        if find_id >= 0:
            self.destination = cli[find_id + len(self.get_asa_key()) + 1:]
            if find_id > 0:
                self.status = 'disable'
            else:
                self.status = 'enable'
            result[(Type.PARAM, 'status', '')] = {'state': State.NOCHANGE, 'value': self.status}
            result[(Type.PARAM, 'event_destination', '')] = {'state': State.NOCHANGE, 'value': self.destination}
           
            return result
        
        return SimpleType.parse_cli(self, cli)
       
    
                
class TemplateAndCollectors(DMObject):
    '''
    Class for NetFlow Collector
    flow-export destination inside 192.168.1.13 2444
    flow-export template timeout-rate 1
    flow-export delay flow-create 20
    flow-export active refresh-interval 30

    '''
    FLOW_EXPORT = 'flow-export'
    FLOW_EXPORT_TIMEOUT_RATE = 'flow-export template timeout-rate'
    FLOW_EXPORT_DELAY_CREATE = 'flow-export delay flow-create'
    FLOW_EXPORT_REFRESH_RATE = 'flow-export active refresh-interval'
    config = {}
   
    def __init__(self):
        '''
        Constructor
        '''
        self.interface = None
        DMObject.__init__(self, TemplateAndCollectors.__name__)
       
        self.response_parser = self.ignore_msg_response_parser
        
        self.register_child(DMList('NetFlowCollectors', NetFlowCollectors, asa_key='flow-export destination'))
        self.register_child(TemplateTimeout("template_timeout_rate", self.FLOW_EXPORT_TIMEOUT_RATE))
        self.register_child(DelayFlowCreate("delay_flow_create", self.FLOW_EXPORT_DELAY_CREATE))
        self.register_child(ActiveRefresh("active_refresh_interval", self.FLOW_EXPORT_REFRESH_RATE))
        
        
    def populate_model(self, delta_ifc_key, delta_ifc_cfg_value):
        ''' Populate model '''
        super(TemplateAndCollectors, self).populate_model(delta_ifc_key, delta_ifc_cfg_value)
        
        values = delta_ifc_cfg_value['value']
        for (ifc_type, ifc_key, ifc_name), value in values.iteritems():
            if ifc_key == 'NetFlowCollectors':
                data = util.normalize_param_dict(value['value'])
                data['state'] = value['state']
            else:
                data = {'state': value['state'], 'value': value['value']}
            self.config[(ifc_key, ifc_name)] = data
       
        
        
    def process_collectors(self, no_asa_cfg_stack, asa_cfg_list, translator, value):  
        ''' Process collectors '''
        state = value.get('state', State.CREATE)
        if len(translator.children.values()) > 0:
            child = translator.children.values()[0]
            
            if self.interface:
                child.interface = self.interface
                cli = child.create_cli(value, state)
            else:
                return
        else:
            return
        
        if state != State.DESTROY:
            key = NetFlowCollectors.get_collector_info(value)
            if key in self.parent.collectors and value.get('status', 'enable') == 'enable':
                return
            asa_cfg_list.append(CLIInteraction(cli, response_parser=self.ignore_msg_response_parser))
        else:
            no_asa_cfg_stack.append(CLIInteraction(cli, response_parser=self.ignore_msg_response_parser))
                
            
    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        ''' Translate IFC config to ASA config  '''
        
        self.get_parent().query_collectors()
        self.interface = None
        for (ifc_key, ifc_name), value in self.config.iteritems():
            if not value:
                continue
            translator = self.get_child(ifc_key)
            state = value['state']
            if isinstance(translator, DMList):
                if not self.interface:
                    child = translator.children.values()[0]
                    self.interface = child.get_top().get_utility_nameif()
                self.process_collectors(no_asa_cfg_stack, asa_cfg_list, translator, value)
            else:
                clia = CLIInteraction(translator.create_cli(value, state), response_parser=self.ignore_msg_response_parser)
                if state == State.CREATE or state == State.MODIFY:
                    asa_cfg_list.append(clia)
                elif state == State.DESTROY:
                    no_asa_cfg_stack.append(clia)
            self.config[ifc_key, ifc_name] = None

    @staticmethod
    def ignore_msg_response_parser(response):
        'Ignores some response, otherwise returns original'
        msgs = ["destination already exists", "is being used", "may cause flow-update events"]
        if response:
            for msg in msgs:
                if msg in response:
                    return None
            return response
        else:
            return None
        
class NetFlowCollectors(SimpleType):
    ''' Class to support CLI
    flow-export destination inside 192.168.1.13 2444
    '''
    
    def __init__(self, name, asa_key = "flow-export destination"):
        '''Constructor'''
        
        self.interface = None
        SimpleType.__init__(self, name, asa_key,
            asa_gen_template = 'flow-export destination %(interface)s %(host)s %(port)s',
            response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        
    
            
    def diff_ifc_asa(self, cli):
        ''' Get diff of IFC and ASA '''
        super(NetFlowCollectors, self).diff_ifc_asa(cli)
        
        if self.get_action() == State.MODIFY:
            values = util.normalize_param_dict(self.parse_cli(cli))
            if self.get_collector_info(values) in NetFlowObjects.collectors:
                self.set_action(State.NOCHANGE)
                

    @staticmethod
    def get_collector_info(values):  
        '''Get unique collector info. string '''
        return values.get('host', 'host') + ':' + str(values.get('port', '0')) 
    
    def get_cli(self):
        '''Generate the CLI for this 'flow-export destination' config.
        '''
        assert self.has_ifc_delta_cfg()
        if not self.interface:
            self.interface = self.get_top().get_utility_nameif()
        if self.interface:
            config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
            state = self.delta_ifc_cfg_value['state']
            if 'host' in config and 'port' in config:
                return self.create_cli(config, state)
         
    
    def create_cli(self, values, state):
        ''' Create a CLI string '''
        
        
        no_cmd = ''
        status = values.get('status', 'enable')
        
        key = self.get_collector_info(values)
        if state == State.DESTROY or status == 'disable':
            no_cmd = 'no '
            if key in NetFlowObjects.collectors:
                NetFlowObjects.collectors.pop(key)
        
        values['interface'] = self.interface
        return no_cmd + self.asa_gen_template % values
    

    
    def parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = None):
        ''' Parse CLI '''
        return self.parse_destination(cli)
    
    @staticmethod
    def parse_destination(cli):
        ''' Parse NetFlow destination CLI '''
        result = {}
        if not cli or len(cli) == 0:
            return result
       
        data = cli.split()
        status = 'enable'
        ind = 0
        if cli.startswith('no '):
            status = 'disable'
            ind = 1
        if len(data) >= ind + 5:
            state  = State.NOCHANGE
            result[(Type.PARAM, 'status', 'status')] = {'state': state, 'value': status}
            result[(Type.PARAM, 'interface', 'interface')] = {'state': state, 'value': data[ind + 2]}
            result[(Type.PARAM, 'host', 'host')] = {'state': state, 'value': data[ind + 3]}
            result[(Type.PARAM, 'port', 'port')] = {'state': state, 'value': data[ind + 4]}
            
            
        return result
    
class TemplateTimeout(SimpleType):
    ''' Class to support CLI
    flow-export template timeout-rate 1
    '''
    def __init__(self, name, asa_key):
        '''Constructor'''
        
        SimpleType.__init__(self, name, asa_key,
            response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        
    def get_cli(self):
        '''Generate the CLI for this 'template timeout-rate' config.
        '''
        assert self.has_ifc_delta_cfg()
        
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        if not config:
            return ''
        state = self.delta_ifc_cfg_value['state']
        return self.create_cli({'state': state, 'value':config}, state)
    
    def create_cli(self, value, state):
        ''' Create a CLI string '''
        no_cmd = 'no ' if state == State.DESTROY else ''
        return no_cmd + TemplateAndCollectors.FLOW_EXPORT_TIMEOUT_RATE + ' ' + str(value['value'])
    
    def parse_cli(self, cli):
        ''' Parse CLI '''
        ind  = cli.find(TemplateAndCollectors.FLOW_EXPORT_TIMEOUT_RATE)
        if ind == 0:
            val = cli[len(TemplateAndCollectors.FLOW_EXPORT_TIMEOUT_RATE) + 1:]
            return val
        return None

class DelayFlowCreate(SimpleType):
    ''' Class to support CLI
    flow-export delay flow-create 20
    '''
    def __init__(self, name, asa_key):
        '''Constructor'''
        self.is_removable = True
        SimpleType.__init__(self, name, asa_key,
            response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        
    def get_cli(self):
        '''Generate the CLI for this 'delay flow-create' config.
        '''
        assert self.has_ifc_delta_cfg()
        state = self.delta_ifc_cfg_value['state']
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        
        if not config:
            return ''
        return self.create_cli({'state': state, 'value':config}, state)
    
    def create_cli(self, value, state):
        ''' Create CLI string '''
        no_cmd = 'no ' if state == State.DESTROY else ''
        return no_cmd + TemplateAndCollectors.FLOW_EXPORT_DELAY_CREATE + ' ' + str(value['value'])
    
    def parse_cli(self, cli):
        ''' Parse CLI '''
        ind  = cli.find(TemplateAndCollectors.FLOW_EXPORT_DELAY_CREATE)
        if ind == 0:
            return  cli[len(TemplateAndCollectors.FLOW_EXPORT_DELAY_CREATE) + 1:]
        return None

class ActiveRefresh(SimpleType):
    ''' Class to support CLI
    flow-export active refresh-interval 30
    '''
    def __init__(self, name, asa_key):
        '''Constructor'''
        
        SimpleType.__init__(self, name, asa_key,
            response_parser = TemplateAndCollectors.ignore_msg_response_parser)
        
    def get_cli(self):
        '''Generate the CLI for this 'active refresh-interval' config.
        '''
        assert self.has_ifc_delta_cfg()
        
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        
        if not config:
            return ''
        state = self.delta_ifc_cfg_value['state']
        return self.create_cli({'state': state, 'value':config}, state)
    
    def create_cli(self, value, state):
        ''' Create CLI '''
        
        no_cmd = 'no ' if state == State.DESTROY else ''
        return no_cmd + TemplateAndCollectors.FLOW_EXPORT_REFRESH_RATE + ' ' + str(value['value'])
    
    def parse_cli(self, cli):
        ''' Parse CLI '''
        ind  = cli.find(TemplateAndCollectors.FLOW_EXPORT_REFRESH_RATE)
        if ind == 0:
            return cli[len(TemplateAndCollectors.FLOW_EXPORT_REFRESH_RATE) + 1:]
            
        return None
