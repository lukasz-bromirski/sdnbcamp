'''
Created on Dec 11, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Utilities for working with network services.
'''

PORT_MAP = {
    'tcp': {
        7:      'echo',
        9:      'discard',
        13:     'daytime',
        19:     'chargen',
        20:     'ftp-data',
        21:     'ftp',
        22:     'ssh',
        23:     'telnet',
        25:     'smtp',
        43:     'whois',
        49:     'tacacs',
        53:     'domain',
        70:     'gopher',
        79:     'finger',
        80:     'www',
        101:    'hostname',
        109:    'pop2',
        110:    'pop3',
        111:    'sunrpc',
        113:    'ident',
        119:    'nntp',
        139:    'netbios-ssn',
        143:    'imap4',
        179:    'bgp',
        194:    'irc',
        389:    'ldap',
        443:    'https',
        496:    'pim-auto-rp',
        512:    'exec',
        513:    'login',
        514:    'rsh',
        515:    'lpd',
        517:    'talk',
        540:    'uucp',
        543:    'klogin',
        544:    'kshell',
        554:    'rtsp',
        636:    'ldaps',
        750:    'kerberos',
        1352:   'lotusnotes',
        1494:   'citrix-ica',
        1521:   'sqlnet',
        1720:   'h323',
        1723:   'pptp',
        2049:   'nfs',
        2748:   'ctiqbe',
        3020:   'cifs',
        5060:   'sip',
        5190:   'aol',
        5631:   'pcanywhere-data',
        'cmd':  'rsh',
        'http': 'www',
    },
    'udp': {
        7:      'echo',
        9:      'discard',
        37:     'time',
        42:     'nameserver',
        49:     'tacacs',
        53:     'domain',
        67:     'bootps',
        68:     'bootpc',
        69:     'tftp',
        80:     'www',
        111:    'sunrpc',
        123:    'ntp',
        137:    'netbios-ns',
        138:    'netbios-dgm',
        161:    'snmp',
        162:    'snmptrap',
        177:    'xdmcp',
        195:    'dnsix',
        434:    'mobile-ip',
        496:    'pim-auto-rp',
        500:    'isakmp',
        512:    'biff',
        513:    'who',
        514:    'syslog',
        517:    'talk',
        520:    'rip',
        750:    'kerberos',
        1645:   'radius',
        1646:   'radius-acct',
        2049:   'nfs',
        3020:   'cifs',
        5060:   'sip',
        5510:   'secureid-udp',
        5632:   'pcanywhere-status',
        'http': 'www',
    },
    'tcp-udp': {
        9:      'discard',
        7:      'echo',
        49:     'tacacs',
        53:     'domain',
        80:     'www',
        111:    'sunrpc',
        496:    'pim-auto-rp',
        517:    'talk',
        750:    'kerberos',
        2049:   'nfs',
        3020:   'cifs',
        5060:   'sip',
        'http': 'www',
    }
}

def get_port_cli(protocol, port):
    '''
    Returns the CLI string for the given protocol (tcp, udp, or tcp-udp) and
    port (which can be a name or number)
    '''

    if protocol in ('tcp', 'udp', 'tcp-udp'):
        if isinstance(port, basestring):
            if port.isdigit():
                key = int(port)
            else:
                key = port = port.strip().lower()
        else:
            key = port
        return PORT_MAP[protocol].get(key, port)
    else:
        return port

ICMP_TYPE_MAP = {
    'icmp': {
        0:  'echo-reply',
        3:  'unreachable',
        4:  'source-quench',
        5:  'redirect',
        6:  'alternate-address',
        8:  'echo',
        9:  'router-advertisement',
        10: 'router-solicitation',
        11: 'time-exceeded',
        12: 'parameter-problem',
        13: 'timestamp-request',
        14: 'timestamp-reply',
        15: 'information-request',
        16: 'information-reply',
        17: 'mask-request',
        18: 'mask-reply',
        30: 'traceroute',
        31: 'conversion-error',
        32: 'mobile-redirect'
    },
    'icmp6': {
        1:   "unreachable",
        2:   "packet-too-big",
        3:   "time-exceeded",
        4:   "parameter-problem",
        128: "echo",
        129: "echo-reply",
        130: "membership-query",
        131: "membership-report",
        132: "membership-reduction",
        133: "router-solicitation",
        134: "router-advertisement",
        135: "neighbor-solicitation",
        136: "neighbor-advertisement",
        137: "neighbor-redirect",
        138: "router-renumbering",
    }
}

def get_icmp_type_cli(protocol, icmp_type):
    '''
    Returns the CLI string for the given protocol (icmp or icmp6) and type
    (which can be a name or number)
    '''

    if protocol in ('icmp', 'icmp6'):
        if isinstance(icmp_type, basestring):
            if icmp_type.isdigit():
                key = int(icmp_type)
            else:
                key = icmp_type = icmp_type.strip().lower()
        else:
            key = icmp_type
        return ICMP_TYPE_MAP[protocol].get(key, icmp_type)
    else:
        return icmp_type
