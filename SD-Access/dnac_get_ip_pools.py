#! /usr/bin/env python3

import requests
import urllib3
from requests.auth import HTTPBasicAuth
from prettytable import PrettyTable

#
# DNAC parameters needs to be defined here
#

dnac_devices = PrettyTable(['Hostname','Platform Id','Software Type','Software Version','Up Time' ])
dnac_devices.padding_width = 1

dnac_global_ip_pool = PrettyTable(['Pool Name','Prefix', 'DNS IP' ])
dnac_global_ip_pool.padding_width = 1

# Silence the insecure warning due to SSL Certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
              'content-type': "application/json",
              'x-auth-token': ""
          }


def dnac_login(host, username, password):
    url = "https://{}/api/system/v1/auth/token".format(host)
    try:
        response = requests.request("POST", url, auth=HTTPBasicAuth(username, password),
                                    headers=headers, verify=False)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    return response.json()["Token"]


def global_ip_pool_list(dnac, token):
    url = "https://{}/dna/intent/api/v1/global-pool".format(dnac['host'])
    headers["x-auth-token"] = token
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)

    data = response.json()
    for item in data['response']:
        dnac_global_ip_pool.add_row([item["ipPoolName"],item["ipPoolCidr"],item["dnsServerIps"][0]])


login = dnac_login(dnac["host"], dnac["username"], dnac["password"])
global_ip_pool_list(dnac, login)
print(dnac_global_ip_pool)
