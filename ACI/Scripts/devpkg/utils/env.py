'''
Created on Jul 26, 2013

@author: jeffryp

Copyright (c) 2013 by Cisco Systems, Inc.
All rights reserved.
'''

import syslog

def debug(message, severity=1):
    '''
    Display a debug message.

    Args:
        message: Message to display
        severity: Severity of the message
    '''
    syslog.syslog(message)
    try:
        import Insieme.Logger as Logger
        Logger.log(Logger.INFO, message)
    except Exception as e:
        print message
