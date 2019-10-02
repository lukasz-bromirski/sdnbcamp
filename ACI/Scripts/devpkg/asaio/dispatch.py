'''
Created on Jun 28, 2013

@author: feliu

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

This module contains the HttpDispatch class that uses the device access info to
connect to the device and deliver CLI commands.

To interact with an ASA device, create one instance of an HttpDispatch per
device.

To send configuration to a device, call the make_command_messenger() function of
the HttpDispatch instance for each list of commands to be sent.  This will
return an HttpCommandMessenger instance.  Call the get_results() function of the
HttpCommandMessenger instance to send the commands to the ASA device.  The
response from the ASA will be returned as a list of CLIResult objects.

For example:
dispatcher = HttpDispatch({'host': '172.23.204.63', 'port': 443,
                           'creds': {'username': 'cisco', 'password': 'cisco'}}
cli_holder = [CLIInteraction('domain-name cisco.com')]
messenger = dispatcher.make_command_messenger(cli_holder)
messenger.get_results()

To read the configuration from the device, call the make_read_config_messenger()
function of the HttpDispatch instance.  This will return an
HttpReadConfigMessenger instance which is file-like.  It has read(), readline()
and next() functions.  It is iterable and can be used in a for/in loop.

For example:
messenger = dispatcher.make_read_config_messenger()
print messenger.read()

To send show commands to a device, call the make_shows_messenger() function of
the HttpDispatch instance with a list of show commands to be sent.  This will
return an HttpShowsMessenger instance which is file-like.  It has read(),
readline() and next() functions.  It is iterable and can be used in a for/in
loop.

For example:
messenger = dispatcher.make_shows_messenger(['show version'])
for line in messenger:
    print line,

'''

import time
import urllib
import urllib2
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from asaio.cli_interaction import CLIResult
from utils import env

ADMIN_PATH = 'admin/'
CONFIG_PATH = 'config'
TAG_PATH = 'tag-switching'

DEFAULT_TIMEOUT = 60

class HttpDispatch:
    '''
    Dispatch communications via HTTPS to the device through Messengers that
    HTTPDispatch creates.
    
    '''

    def __init__(self, device):
        '''
        @param device: format example {'host': '172.23.204.63',
                                       'port': 443,
                                       'creds': {
                                           'username': 'cisco',
                                           'password': 'cisco'
                                       }
                                      }
        '''

        self.username = device['creds']['username']
        self.password = device['creds']['password']
        address = device.get('host')
        if not address:
            address = device.get('ip')
        self.baseUrl = ('https://' + address + ':' +
                        str(device['port']) + '/' + ADMIN_PATH)

    def create_connection(self, url):
        'Initiate an HTTPS connection for a Messenger implementation'

        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(
            realm=None,
            uri=url,
            user=self.username,
            passwd=self.password)
        return urllib2.build_opener(urllib2.HTTPBasicAuthHandler(
            password_manager))

    @staticmethod
    def encode_url_path(show_commands):
        url = []
        for command in show_commands:
            if len(url) > 0:
                url.append('/')
            url.append(urllib.quote(command, safe=''))
        return ''.join(url)

    def make_exec_url(self, path):
        # TODO: Add support for system and context
        return self.baseUrl + 'exec/' + path

    def make_handler_url(self, command):
        # TODO: Add support for system and context
        return self.baseUrl + command

    def make_command_messenger(self, cli_holder):
        '''
        Make a command messenger to send configuration and exec commands.
    
        The cli_holder parameter is a list of CLIInteraction objects that
            contain the commands to send.
            
        '''

        return HttpCommandMessenger(self, cli_holder)

    def make_read_config_messenger(self):
        'Make a read config messenger to read the config from the device'

        return HttpReadConfigMessenger(self)

    def make_shows_messenger(self, show_commands):
        '''
        Make a shows messenger to send show commands and get the responses.

        The show_commands parameter is a list of show commands.

        '''

        return HttpShowsMessenger(self, show_commands)

    def make_sts_write_messenger(self, table):
        '''
        Make an STS table write messenger to send STS table to ASA.
        '''
        return HttpSTSWriteMessenger(self, table)

    def make_sts_audit_write_messenger(self, table):
        '''
        Make an STS table audit messenger to send STS table to ASA.
        '''
        return HttpSTSAuditWriteMessenger(self, table)

    def make_sts_audit_read_messenger(self, sts):
        '''
        Make an STS audit read messenger to query STS table from ASA.
        '''
        return HttpSTSAuditReadMessenger(self, sts)

class FileLikeMessenger:
    'Base class for messengers that are file-like'

    def __init__(self, dispatch, url):
        connection = dispatch.create_connection(url)
        env.debug('Command (' + url + ') started')

        start_time = time.clock()
        self.response = connection.open(fullurl=url, timeout=DEFAULT_TIMEOUT)
        elapsed_time = time.clock() - start_time
        env.debug('GET ' + url + ' Time=' + str(elapsed_time) + ' seconds')

    def __iter__(self):
        return self.response.__iter__()

    def next(self):
        return self.response.next()

    def read(self, size=-1):
        return self.response.read(size)

    def readline(self, size=-1):
        return self.response.readline(size)

    def readlines(self, sizehint=0):
        return self.response.readlines(sizehint)

class HttpCommandMessenger:
    '''
    Send configuration and exec commands to the device and parse the responses

    This class should not be instantiated directly.  Instead, call
    HttpDispatch.make_command_messenger().

    '''

    CLI_TYPE_MAP = {
        'error': CLIResult.ERROR,
        'info': CLIResult.INFO,
        'warning': CLIResult.INFO}

    def __init__(self, dispatch, cli_holder):
        self.dispatch = dispatch
        self.cli_holder = cli_holder
        self.xml = self.get_xml()
        self.url = dispatch.make_handler_url(CONFIG_PATH)

    def get_results(self):
        connection = self.dispatch.create_connection(self.url)
        request = urllib2.Request(
            url=self.url,
            data=self.xml,
            headers={'Content-Type': 'text/xml'})
        env.debug('POST URL = ' + self.url + '\nRequest:\n' + self.xml)

        start_time = time.clock()
        response = connection.open(fullurl=request, timeout=DEFAULT_TIMEOUT)
        body = response.read()
        elapsed_time = time.clock() - start_time
        env.debug('Response:\n' + body + '\nResponse time: ' +
                  str(elapsed_time) + ' seconds.')
        return self.parse_error(body)
     
    def get_xml(self):
        xml = []
        xml.append(('<?xml version="1.0" encoding="ISO-8859-1"?>\n' +
                    '<config-data config-action="merge" errors="continue">\n'))
    
        for i, cli_interaction in enumerate(self.cli_holder):
            xml.append('<cli id="' + str(i) + '">')
            xml.append(escape(cli_interaction.command))
            xml.append('</cli>\n')
            
        xml.append('</config-data>\n')
        return ''.join(xml)
    
    def parse_error(self, response):
        if not self.cli_holder:
            return []
    
        result = [None] * len(self.cli_holder)
        if response:
            root = ElementTree.fromstring(response)
            for error_info in root.findall('.//error-info'):
                cli_id = int(error_info.attrib.get('id'))
                err_type = HttpCommandMessenger.CLI_TYPE_MAP.get(
                    error_info.attrib.get('type'))
                err_msg = error_info.text
        
                if err_type == CLIResult.ERROR and not err_msg:
                    err_msg = 'Command failed'
                if err_msg:
                    cli_interaction = self.cli_holder[cli_id]
                    err_msg = cli_interaction.parse_response(err_msg)
                    result[cli_id] = CLIResult(
                        cli=cli_interaction.command,
                        err_type=err_type,
                        err_msg=err_msg,
                        model_key=cli_interaction.model_key)
        
        return result

class HttpReadConfigMessenger(FileLikeMessenger):
    '''
    Read the configuration from the device
    
    This class should not be instantiated directly.  Instead, call
    HttpDispatch.make_read_config_messenger().
    
    '''

    def __init__(self, dispatch):
        FileLikeMessenger.__init__(self, dispatch, dispatch.make_handler_url(
            CONFIG_PATH))

class HttpShowsMessenger(FileLikeMessenger):
    '''
    Send show commands to the device and return the responses
    
    This class should not be instantiated directly.  Instead, call
    HttpDispatch.make_shows_messenger().
    
    '''

    def __init__(self, dispatch, show_commands):
        FileLikeMessenger.__init__(self, dispatch, dispatch.make_exec_url(
            HttpDispatch.encode_url_path(show_commands)))

class HttpSTSWriteMessenger:
    '''
    Send STS table to the device and parse the responses
    This method sends https://172.23.204.252/admin/tag-switching
    with parameters of table with the following parameter.
    'DATABASE:STS_TABLE\n' \
    'DB_VERSION:1\n' \
    'DB_ACTION:INCR_UPDATE\n' \
    'BODY_TYPE:TABLE\n' \
    'COLS:3,STRING,UINT32,UINT32\n' \
    'ROWS:4\n' \
    'ADD,100,101\n' \
    'ADD,200,201\n' \
    'ADD,300,301\n' \
    'ADD,400,401\n' \
    'END\n'
    The first five fields are fixed for Greenfield, starting at the 6th row,
    it indicates number of rows to update the STS table.
    STS table is not visible in show runn and cannot be modified through CLI.
    This class and HttpsSTSAudi will update the STS table
    This class should not be instantiated directly.  Instead, call
    HttpDispatch.make_sts_table_messenger().
    '''

    def __init__(self, dispatch, sts):
        self.dispatch = dispatch
        self.sts = sts
        self.url = dispatch.make_handler_url(TAG_PATH)

    def get_param(self):
        return self.sts.get_param()
    
    def get_results(self):
        parameter = self.get_param()
        if not parameter:
            return None
        connection = self.dispatch.create_connection(self.url)
        request = urllib2.Request(
            url=self.url,
            data=parameter,
            headers={'Content-Type': 'text/xml'})
        env.debug('POST URL = ' + self.url + '\nRequest:\n' + parameter)

        start_time = time.clock()
        response = connection.open(fullurl=request, timeout=DEFAULT_TIMEOUT)
        body = response.read()
        elapsed_time = time.clock() - start_time
        env.debug('Response:\n' + body + '\nResponse time: ' +
                  str(elapsed_time) + ' seconds.')
        return self.parse_error(body)

    def parse_error(self, response):
        if not self.sts:
            return []
        return self.sts.parse_error(response)

class HttpSTSAuditWriteMessenger(HttpSTSWriteMessenger):
    '''
    This class will update the ASA STS table after processing the audit. 
    The HttpSTSAuditReadMessenger retrieves the STS ASA table and do a comparison 
    with the STS mapping collected from ifc2asa().
    '''
    def get_param(self):
        return self.sts.get_audit_param()

class HttpSTSAuditReadMessenger(HttpSTSWriteMessenger):
    '''
    This class post a request to ASA to query STS table and parse the STS table.
    This class should not be instantiated directly.  Instead, call
    HttpDispatch.query_sts_table_messenger().
    '''
    def get_param(self):
        return self.sts.audit_parameter

    def get_results(self):
        result = HttpSTSWriteMessenger.get_results(self)
        if 'Failed' in result:
            return result
        self.sts.diff_response(result)
        return None
