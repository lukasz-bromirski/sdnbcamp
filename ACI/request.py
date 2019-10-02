#!/usr/bin/python

import glob
import json
import os
import os.path
import requests
import sys
import time
import xml.dom.minidom
import yaml

try:
    cfgFile = sys.argv[1]
except Exception as e:
    print str(e)
    sys.exit(0)

with open( cfgFile, 'r' ) as config:
    config = yaml.safe_load( config )

auth = {
    'aaaUser': {
        'attributes': {
            'name': config['name'],
            'pwd': config['passwd']
            }
        }
    }

status = 0
while( status != 200 ):
    url = 'https://%s/api/aaaLogin.json' % config['host']
    while(1):
        try:
            r = requests.post( url, data=json.dumps(auth), timeout=1, verify=False )
            break;
        except Exception as e:
            print "timeout"
    status = r.status_code
#    print r.text
    cookies = r.cookies
    time.sleep(1)

def runConfig( status, config ):
    tests = config['tests']
    for t in tests:
        type = t['type']
        url = 'https://%s/%s' % (config['host'],t['path'])
        file = t['file']
	passme = t['pass']
	validate = t['check']

        if type=='file':
            with open(file,'r') as package:
                if( status==200) and ('wait' in t):
                    time.sleep( t['wait'] )
                else:
                    raw_input( 'Hit return to upload %s' % file )

                r = requests.post( url, 
                                   cookies=cookies,
                                   files={'file':package}, verify=False )
                result = xml.dom.minidom.parseString( r.text )
                status = r.status_code
                #print '++++++++ RESPONSE (%s) ++++++++' % file
                #print result.toprettyxml()
                #print '-------- RESPONSE (%s) --------' % file
                #print status
		print 
		print passme
		print
		print validate
		print

        elif type=='xml':
            with open( file, 'r' ) as payload:
                if( status==200) and ('wait' in t):
                    time.sleep( t['wait'] )
                else:
                    raw_input( 'Hit return to process %s' % file )

                data = payload.read()
                # print '++++++++ REQUEST (%s) ++++++++' % file
                # print data
                # print '-------- REQUEST (%s) --------' % file 
                url = 'https://%s/api/node/mo/.xml' % config['host']
                r = requests.post( url,
                                   cookies=cookies,
                                   data=data, verify=False )
                result = xml.dom.minidom.parseString( r.text )
                status = r.status_code
                # print '++++++++ RESPONSE (%s) ++++++++' % file
                # print result.toprettyxml()
                # print '-------- RESPONSE (%s) --------' % file
                # print status
		print
		print passme
		print
		print validate
		print

        else:
            print 'Unknown type:', type

runConfig( status, config )
