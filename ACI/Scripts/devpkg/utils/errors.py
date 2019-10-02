'''
Created on Oct 9, 2013

Exception classes for device package

@author: dli
'''
class ConnectionError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class ConfigurationError(Exception):
    def __init__(self, fault_list):
        self.fault_list = fault_list

class IFCConfigError(ConfigurationError):
    def __init__(self, fault_list):
        ConfigurationError.__init__(self, fault_list)

class ASACommandError(ConfigurationError):
    def __init__(self, fault_list):
        ConfigurationError.__init__(self, fault_list)
