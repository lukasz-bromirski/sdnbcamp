'''
Created on Dec 11, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.

Utilities for working with network protocols.
'''

PROTOCOL_MAP = {
    0:       'ip',
    1:       'icmp',
    2:       'igmp',
    4:       'ipinp',
    6:       'tcp',
    9:       'igrp',
    17:      'udp',
    47:      'gre',
    50:      'esp',
    51:      'ah',
    58:      'icmp6',
    88:      'eigrp',
    89:      'ospf',
    94:      'nos',
    103:     'pim',
    108:     'pcp',
    109:     'snp',
    'ipsec': 'esp',
    'pptp':  'gre'
}

def get_cli(protocol):
    '''
    Returns the CLI string for the given protocol (which can be a name or number)
    '''

    if isinstance(protocol, basestring):
        if protocol.isdigit():
            key = int(protocol)
        else:
            key = protocol = protocol.strip().lower()
    else:
        key = protocol
    return PROTOCOL_MAP.get(key, protocol)
