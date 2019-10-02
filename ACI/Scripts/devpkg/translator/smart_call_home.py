'''
Created on Dec 18, 2013

@author: linlilia

Copyright (c) 2013 by Cisco Systems

This module is for the support of Smart Call Home.

In current phase, only Anonymous Reporting, the subfeature of SCH, is supported to allow Cisco
to anonymously receive minimal error and health information from the device.

CLI to enable the Anonymous Reporting feature and create a new anonymous profile:
    call-home reporting anonymous
'''
from translator.base.dmobject import DMObject
from base.dmboolean import DMBoolean

ANONYMOUS_REPORTING_CLI = 'call-home reporting anonymous'

class SmartCallHome(DMObject):
    '''
    Container of Smart Call Home Feature
    '''
    def __init__(self):
        DMObject.__init__(self, SmartCallHome.__name__)
        self.register_child(DMBoolean(ifc_key = 'anonymous_reporting', asa_key = ANONYMOUS_REPORTING_CLI, on_value = 'enable'))
