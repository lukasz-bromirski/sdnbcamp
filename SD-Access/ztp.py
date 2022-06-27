# Importing cli module
from cli import configure, cli
import re
import json
import time

pod = 9

def get_model():
    show_version = cli('show version')
    try:
        serial = re.search(r"Model Number\s+:\s+(\S+)", show_version).group(1)
    except AttributeError:
        serial = re.search(r"Processor board ID\s+(\S+)", show_version).group(1)
    return serial

def get_serial():
    show_version = cli('show version')
    
    try:
        serial = re.search(r"System Serial Number\s+:\s+(\S+)", show_version).group(1)
    except AttributeError:
        serial = re.search(r"Processor board ID\s+(\S+)", show_version).group(1)
    return serial

def main(): 
    print(f"*** Model number: {get_model()}, serial number: {get_serial()} ***")

    import cli

    print("Configure aaa, credentials and basic settings\n\n")

    cli.configurep(["hostname POD{}_SW3".format(pod), "end"])

    cli.configurep(["service timestamps debug datetime msec", "service timestamps log datetime msec", "end"])

    cli.configurep(["aaa new-model", "aaa authentication login default local", "aaa authorization exec default local", "aaa session-id common", "end"])
    cli.configurep(["username cliadmin privilege 15 password Admin{}sisko$".format(pod), "end"])
    cli.configurep(["enable password Admin{}sisko$".format(pod), "end"]) 

    cli.configurep(["snmp-server community cisco RO", "end"])
    cli.configurep(["snmp-server community Admin{}sisko$ RW".format(pod), "end"])

    print("Configure IP interfaces and routing, disable Vlan1 SVI\n\n")

    cli.configurep(["ip routing", "end"])
    cli.configurep(["int Vlan1","no ip address", "shut", "end"])

    cli.configurep(["int gi1/0/11","no switchport", "ip address 10.1{}.2.3 255.255.255.0".format(pod), "no shut", "end"])
    cli.configurep(["interface Loopback0", "ip address 10.1{}.127.3 255.255.255.255".format(pod), "end"])
    cli.configurep(["ip route 0.0.0.0 0.0.0.0 10.1{}.2.254".format(pod), "end"])

    print("Configure misc. stuff\n\n")

    cli.configurep(["archive", "log config", "logging enable", "notify syslog contenttype plaintext", "end"])

    cli.configurep(["line con 0", "exec-timeout 0 0", "end"])

    cli.executep("copy running-config startup-config")
    
    print("\n\n *** Executing show ip interface brief  *** \n\n")
    cli_command = "sh ip int brief | e down"
    cli.executep(cli_command)

    print("\n\n *** ZTP Day0 Python Script Execution Complete *** \n\n")

if __name__ in "__main__":
    main()

