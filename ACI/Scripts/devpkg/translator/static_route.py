#
# Copyright (c) 2013 by Cisco Systems, Inc.
#
'''
Created on Jun 28, 2013

@author: feliu

This is the static route class.

'''

import translator
from translator.state_type import Type, State
from translator.base.dmobject import DMObject
from translator.base.dmlist import DMList
from translator.base.simpletype import SimpleType
import utils.util as util


class IntStaticRoute(DMObject):
    def __init__(self):
        DMObject.__init__(self, 'IntStaticRoute')
        self.register_child(RouteList("route", "internal"))
        self.register_child(RouteList("ipv6 route", "internal"))

class ExtStaticRoute(DMObject):
    def __init__(self):
        DMObject.__init__(self, 'ExtStaticRoute')
        self.register_child(RouteList("route", "external"))
        self.register_child(RouteList("ipv6 route", "external"))

class RouteList(DMList):
    def __init__(self, cmd_prefix, connector):
        DMList.__init__(self, 'ipv6route', IPv6Route) if 'ipv6' in cmd_prefix \
            else DMList.__init__(self, 'route', Route)
        self.asa_key = cmd_prefix
        self.connector = connector
        self.cmd_prefix = cmd_prefix

    def is_my_cli(self, cli):
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(self.connector)
        if not connector:
            return False
        asa_key = self.cmd_prefix + " " + connector.get_nameif()
        return str(cli).startswith(asa_key)

class Route(SimpleType):
    '''
    This class represents the holder of all IPv4 static routes.
    '''

    def __init__(self, name):
        SimpleType.__init__(self, name,
                            asa_gen_template = 'route %(interface)s %(network)s %(netmask)s %(gateway)s %(metric)s',
                            response_parser = static_route_response_parser,
                            defaults={'metric': '1'})

    def get_cli(self):
        value = self.get_value_with_connector()
        return ' '.join(str(self.asa_gen_template % value).split())

    def get_value_with_connector(self):
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        nameif = None
        # The connector_name can be determined by the instance name of the class, which is
        # the interface label ('internal' or 'external') defined by us via the device_specification.xml.
        # self.parent is the DMList, self.parent.parent is either IntStaticRoute or ExtStaticRoute.
        connector_name = 'internal' if self.parent.parent.ifc_key == 'IntStaticRoute' else 'external'
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(connector_name)
        if connector:
            nameif = connector.get_nameif()

        'Take care of defaults'
        if self.defaults:
            #filling the default values for missing parameters
            if isinstance(value, dict):
                for name in self.defaults:
                    value[name] = value.get(name, self.defaults[name])
        if nameif:
            value['interface'] = nameif

        return value

    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        value = self.get_value_with_connector()
        'Prevent the deletion of route on management interface or IFC will not able to connect to the ASA'
        self.is_removable = value.get('interface') != 'management'
        return SimpleType.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def create_asa_key(self):
        '''Create the the asa key identifies this object, everything except 'metric' make up the key
        @return str
        '''
        value = self.get_value_with_connector()
        return 'route %(interface)s %(network)s %(netmask)s %(gateway)s' % value

    # We don't need to override parse_multi_parameter_cli because the CLI from the device
    # will always have the optional parameter 'metric' to feed into asa_gen_template in this case.

class IPv6Route(Route):
    '''
    This class represents the holder of all IPv6 static routes.
    '''

    def __init__(self, name):
        '''@todo: use Route.__init__ instead of SimpleType.__init__
           Route.__init__(self, name, defaults=None, asa_gen_template = 'ipv6 route %(interface)s %(prefix)s %(gateway)s')
        '''
        SimpleType.__init__(self, name,
                            asa_gen_template = 'ipv6 route %(interface)s %(prefix)s %(gateway)s %(hop_count)s %(tunneled)s',
                            defaults = {'hop_count': '', 'tunneled': ''},
                            response_parser = static_route_response_parser)

    def normalize_ipv6_values(self, value):
        '''
        @param value - is a dictionary that contains ipv6 prefix and gateway.
        '''
        value['prefix'] = util.normalize_ipv6_address(value['prefix'])
        value['gateway'] = util.normalize_ipv6_address(value['gateway'])
        return value

    def get_cli(self):
        value = self.get_value_with_connector()
        value = self.normalize_ipv6_values(value)
        if value['hop_count'] and int(value['hop_count']) == 1: # Default hop count
            # Do not generate default hop count in CLI, it's not only not needed, but also
            # may cause mismatch to the CLI from ASA during audit because the default hop
            # count is not store on ASA.
            value['hop_count'] = ''
        return ' '.join(str(self.asa_gen_template % value).split())

    def get_value_with_connector(self):
        assert self.has_ifc_delta_cfg()
        value = util.normalize_param_dict(self.delta_ifc_cfg_value['value'])
        nameif = None
        # The connector_name can be determined by the instance name of the class, which is
        # the interface label ('internal' or 'external') defined by us via the device_specification.xml.
        # self.parent is the DMList, self.parent.parent is either IntStaticRoute or ExtStaticRoute.
        connector_name = 'internal' if self.parent.parent.ifc_key == 'IntStaticRoute' else 'external'
        firewall = self.get_ancestor_by_class(translator.firewall.Firewall)
        connector = firewall.get_connector(connector_name)
        if connector:
            nameif = connector.get_nameif()

        'Take care of defaults'
        if self.defaults:
            #filling the default values for missing parameters
            if isinstance(value, dict):
                for name in self.defaults:
                    value[name] = value.get(name, self.defaults[name])
        if nameif:
            value['interface'] = nameif
        return value

    def create_asa_key(self):
        '''Create the the asa key identifies this object, everything except 'metric' make up the key
        @return str
        '''
        value = self.get_value_with_connector()
        value = self.normalize_ipv6_values(value)
        'Prevent the deletion of route on management interface or IFC will not able to connect to the ASA'
        self.is_removable = value.get('interface') != 'management'
        return 'ipv6 route %(interface)s %(prefix)s %(gateway)s' % value

    def parse_multi_parameter_cli(self, cli):
        '''Override the default implementation in case the CLI does not match asa_gen_template due to optional
        parameter
        '''
        'Take care of the mandatory parameters'
        result = SimpleType.parse_multi_parameter_cli(self, cli, alternate_asa_gen_template = 'ipv6 route %(interface)s %(prefix)s %(gateway)s')

        'Take care of the optional parameters'
        for name, value  in self.defaults.iteritems():
            result[(Type.PARAM, name, '')] = {'state': State.NOCHANGE, 'value': value}
        tokens = cli.split()
        if len(tokens) == 5:
            return result #no optional parameter

        option = tokens[5]
        if option == 'tunneled':
            result[Type.PARAM, 'tunneled', '']['value'] = option
        elif option:
            result[Type.PARAM, 'hop_count', '']['value'] = option

        return result


def static_route_response_parser(response):
    '''
    Ignores expected INFO, WARNING, and error in the response, otherwise returns original.
    '''

    if response:
        msgs_to_ignore = ('INFO:',
                          'WARNING:',
                          'No matching route to delete')
        found_msg_to_ignore = False
        for msg in msgs_to_ignore:
            if msg in response:
                found_msg_to_ignore = True
    return None if response and found_msg_to_ignore else response
