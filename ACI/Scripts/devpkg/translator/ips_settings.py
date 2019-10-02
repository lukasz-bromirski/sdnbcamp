'''
Created on Jan 10, 2014

@author: tsnguyen
IPS Settings Class
'''



from translator.base.simpletype import SimpleType
from translator.state_type import Type, State
import utils.util as util
import asaio.cli_interaction as cli_interaction


class IPSSubCommands(SimpleType):
    '''
    Class for IPS Sub Command in service policy
    '''


    def __init__(self):
        '''
        Constructor
        '''

        SimpleType.__init__(self, ifc_key = 'IPSSettings', asa_key = 'ips',
                            asa_gen_template='ips %(operate_mode)s %(fail_mode)s',
                            response_parser = cli_interaction.ignore_warning_response_parser)



    def get_cli(self):
        '''Generate the CLI for this IPS config.
        '''
        if not self.has_ifc_delta_cfg():
            return ''
        config = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])

        sensor = config.get("sensor")
        if sensor:
            return  (self.asa_gen_template % config) + ' sensor ' + sensor
        return self.asa_gen_template % config



    def parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = None):
        ''' Parse parameters '''
        result = {}
        data = cli.split()
        state = State.MODIFY
        result[(Type.PARAM, 'operate_mode', '')] = {'state': state, 'value': ''}
        result[(Type.PARAM, 'fail_mode', '')] = {'state': state, 'value': ''}
        if len(data) >= 3:
            result[Type.PARAM, 'operate_mode', '']['value'] = data[1]
            result[Type.PARAM, 'fail_mode', '']['value'] = data[2]
            if len(data) == 5:
                result[(Type.PARAM, 'sensor', '')] = {'state': state, 'value': ''}
                result[Type.PARAM, 'sensor', '']['value'] = data[4]

        return result

