import sys
import requests
from requests.auth import HTTPBasicAuth
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
              'content-type': "application/json",
              'x-auth-token': ""
          }

def dnac_login(host, username, password):
    url = "https://{}/api/system/v1/auth/token".format(host)
    response = requests.request("POST", url, auth=HTTPBasicAuth(username, password),
                                headers=headers, verify=False)
    return response.json()["Token"]

if len(sys.argv) != 3:
    print ("""Usage:
    PODX_CORE_SW_border_config.py <pod_number> <core_sw_number>
    
    ex. PODX_R1R2_border_config 5 2 (for POD5, CORE_SW2)""")
    exit(1)

pod = sys.argv[1]
core = sys.argv[2]

if ((int(pod) < 1) or (int(pod) >5)):
    print ("<pod_number> must be from 1 to 5")
    exit (1)

if ((int(core) < 1) or (int(core) >2)):
    print ("<core_sw_number> must be either 1 or 2")
    exit (1)

host = "10.1" + pod + ".1.11"
password = 'Admeen' + pod + 'sisko'
token = dnac_login(host, 'admin', password)

headers["x-auth-token"] = token
uri = "https://10.1" + pod + ".1.11/dna/intent/api/v1/business/sda/border-device?deviceIPAddress=10.1" + pod + ".127.10" + core
req = requests.get(uri, headers=headers, verify=False)
bcfg = req.json()['deviceSettings']['extConnectivitySettings'][0]['l3Handoff']
#print ("Index 0: \n" + json.dumps((bcfg), indent=4))
#print ("Index 1: \n" + json.dumps((bcfg[1]), indent=4))

vlan1 = str(bcfg[0]['vlanId'])
vlan2 = str(bcfg[1]['vlanId'])

peer1 = str(bcfg[0]['localIpAddress']).split('/')[0]
peer1v6 = str(bcfg[0]['localIpv6Address']).split('/')[0]
my1 = str(bcfg[0]['remoteIpAddress']).split('/')[0]
my1v6 = str(bcfg[0]['remoteIpv6Address'])

peer2 = str(bcfg[1]['localIpAddress']).split('/')[0]
peer2v6= str(bcfg[1]['localIpv6Address']).split('/')[0]
my2 = str(bcfg[1]['remoteIpAddress']).split('/')[0]
my2v6 = str(bcfg[1]['remoteIpv6Address'])

print
print ("vlan " + vlan1)
print (" name POD" + pod + "_R" + core + "_VN1")
print
print ("vlan " + vlan2)
print (" name POD" + pod + "_R" + core + "_VN2")
print
print ("interface Gi1/" + pod)
print (" switchport trunk allowed vlan " + vlan1 + "," + vlan2)
print 
print ("interface Vlan " + vlan1)
print (" ip address " + my1 + " 255.255.255.252")
print (" ipv6 address " + my1v6)
print (" no shutdown")
print
print ("interface Vlan " + vlan2)
print (" ip address " + my2 + " 255.255.255.252")
print (" ipv6 address " + my2v6)
print (" no shutdown")
print
print ("router bgp 65001")
print (" neighbor " + peer1 + " remote-as 6550" + pod)
print (" neighbor " + peer2 + " remote-as 6550" + pod)
print (" neighbor " + peer1v6 + " remote-as 6550" + pod)
print (" neighbor " + peer2v6 + " remote-as 6550" + pod)
print (" !")
print (" address-family ipv4 unicast")
print (" neighbor " + peer1 + " default-originate")
print (" neighbor " + peer2 + " default-originate")
print (" !")
print (" address-family ipv6 unicast")
print (" neighbor " + peer1v6 + " activate")
print (" neighbor " + peer1v6 + " default-originate")
print (" neighbor " + peer2v6 + " activate")
print (" neighbor " + peer2v6 + " default-originate")
print