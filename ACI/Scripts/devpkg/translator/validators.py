'''
Created on Oct 18, 2013

Module for common validators, such as IntegerValidator, StringValidator, EnumValidator, TimeValidator

Copyright (c) 2013 by Cisco Systems

@author: dli
'''
import re
import socket, struct
from array import array
from utils.service import ICMP_TYPE_MAP, PORT_MAP
from utils.protocol import PROTOCOL_MAP

class Validator:
    'Base validator'
    def validate(self, value):
        '@return None if value is valid, otherwise an error message, a fault tuple, or list of fault tuples'
        return None

class TimeValidator(Validator):
    'Validator for check if a value is in the valid range'
    def __init__(self, min, max, allow0 = False):
        '''
        @param min: str of the form 'hh:mm:ss'
            to indicate the minimum value of the valid range
        @param max: str of the form 'hh:mm:ss'
            to indicate the maximum value of the valid range
        @param allow0: boolean
            to indicate if '0:0:0' is allowed
        '''
        self.min = min
        self.max = max
        self.allow0 = allow0

    @staticmethod
    def time2integer(t):
        '@return the integer value in seconds corresponding to a time value of the format "h:m:s"'
        tokens = t.split(':')
        return int(tokens[0])*3600 + int(tokens[1])*60 + int(tokens[2])

    def validate(self, value):
        '@return None if value is valid, or an error message'
        if not value:
            return None
        err_msg = 'The value is not in the range of ' + self.min + ' to ' + self.max
        try:
            value = TimeValidator.time2integer(value)
            if value == 0 and self.allow0:
                return None
            if (value < TimeValidator.time2integer(self.min) or
                value > TimeValidator.time2integer(self.max)):
                return err_msg
        except:
            return err_msg

class IPv4AddressValidator(Validator):
    'Validator for check if a value is a valid IP v4 address'
    def validate(self, value):
        '@return None if value is valid IP address, or an error message'
        err_msg = "The value is not a valid IP v4 address"
        try:
            socket.inet_pton(socket.AF_INET, value)
        except:
            return err_msg

class IPv6AddressValidator(Validator):
    'Validator for check if a value is a valid IP v6 address'
    def validate(self, value):
        '@return None if value is valid IP address, or an error message'
        err_msg = "The value is not a valid IP v4 address."
        try:
            socket.inet_pton(socket.AF_INET6, value)
        except:
            return err_msg

class IPAddressValidator(Validator):
    'Validator for check if a value is a valid IP address, IPv4 or IPv6'

    def validate(self, value):
        '@return None if value is valid IP address, or an error message'
        is_ipv4 = lambda x: not IPv4AddressValidator().validate(x)
        is_ipv6 = lambda x: not IPv6AddressValidator().validate(x)

        return None if is_ipv4(value) or is_ipv6(value) else "The value is not a valid IP address."

class IPAddressRangeValidator(Validator):
    'Validator for check if a value is valid IP address range, in the format of start_address-end_address'

    def validate(self, value):
        '@return None if value is valid IP address range, or an error message'
        err_msg = "The value is not a valid IP address range, which should be of the format <start_address>-<end_address>."
        try:
            tokens = value.split('-')
            if (not tokens) or (len(tokens) != 2):
                return err_msg

            is_ipv4 = lambda x: not IPv4AddressValidator().validate(x)
            is_ipv6 = lambda x: not IPv6AddressValidator().validate(x)
            ipv4addres2long = lambda x: long(''.join(["%02X" % long(i) for i in x.split('.')]), 16)
            def ipv6addres2long(address):
                """
                The code is copied f from http://stackoverflow.com/questions/2631588/converting-ipv4-or-ipv6-address-to-a-long-for-comparisons
                """
                addr = array('L', struct.unpack('!4L', socket.inet_pton(socket.AF_INET6, address)))
                addr.reverse()
                return sum(addr[i] << (i * 32) for i in range(len(addr)))

            if is_ipv4(tokens[0]) and is_ipv4(tokens[1]):
                return None if ipv4addres2long(tokens[0]) <= ipv4addres2long(tokens[1]) else err_msg
            if is_ipv6(tokens[0]) and is_ipv6(tokens[1]):
                return None if ipv6addres2long(tokens[0]) <= ipv6addres2long(tokens[1]) else err_msg
            return err_msg
        except:
            return err_msg


class IPv4NetmaskValidator():
    'Validator for check if a value is valid IP v4 network mask'

    def validate(self, value):
        '@return None if value is valid IP v4 network mask, or an error message'
        err_msg = "The value is not a valid IPv4 network mask."
        try:
            tokens = [int(x) for x in value.split('.')]
            if (not tokens) or (len(tokens) != 4):
                return err_msg
            'bin_mask is the string of mask in binary format, e.g. 11111111111111111111110000000000'
            bin_mask = ('{:>08b}'*4).format(*tokens)
            'a valid netmask must have all 1s at the start of its bin_ mask, and all 0s at the end of bin_mask'
            return None if re.match('^1+0+$', bin_mask) else err_msg
        except:
                return err_msg

class IPAddressSubnetValidator(Validator):
    'Validator for check if a value is valid IP address range, in the format of ip-address/prefix-length or mask'

    def validate(self, value):
        '@return None if value is valid IP subnet, or an error message'
        err_msg = "The value is not a valid IP subnet address, which should be of the format <ipv4_address>/<network_mask> or <ipv6_address>/<prefix_length>."
        try:
            tokens = value.split('/')
            if (not tokens) or (len(tokens) != 2):
                return err_msg

            is_ipv4 = lambda x: not IPv4AddressValidator().validate(x)
            is_ipv6 = lambda x: not IPv6AddressValidator().validate(x)
            is_ipv4_nework_mask = lambda x: not IPv4NetmaskValidator().validate(x)
            def is_ipv6_prefix_length(length):
                try:
                    n = int(length)
                    return n >=0 and n <= 128
                except:
                    return False

            if is_ipv4(tokens[0]) and is_ipv4_nework_mask(tokens[1]):
                return None
            if is_ipv6(tokens[0]) and is_ipv6_prefix_length(tokens[1]):
                return None
            return err_msg
        except:
            return err_msg

class VersionFQDNValidator(Validator):
    "Validator for FQDN object as network object. The value is in the form of: {v4|v6} <fqdn-string>"

    def validate(self, value):
        '@return None if value is in the form of: {v4|v6} <fqdn-string>'
        err_msg = "The value is not a valid FQDN, which should be of the format: {v4|v6} <fqdn-string>."
        try:
            tokens = value.split()
            if (not tokens) or (len(tokens) != 2):
                return err_msg
            if not (tokens[0] in ['v4', 'v6']):
                return err_msg
            return None if re.match('(?=^.{1,254}$)(^(?:(?!\d+\.)[a-zA-Z0-9_\-]{1,63}\.?)+(?:[a-zA-Z]{2,})$)', tokens[1]) else err_msg
        except:
            return err_msg


class ICMPTypeValidator(Validator):
    """Validator for ICMP type. The value is number between 0 and 255, or a name in ICMP_TYPE_MAP
    """

    def __init__(self, protocol):
        """
        @param protocol: str
            The protocol for the ICMP type, either icmp or icmp6
        """
        self.protocol = protocol
        self.suffix = "6" if protocol == 'icmp6' else ""

    def validate(self, value):
        err_msg = "Illegal ICMP%s type. It must be an integer between 0 and 255, or a type name." % self.suffix
        try:
            n = int(value)
            return None if (n >= 0 and n <= 255) else err_msg
        except:
            return None if str(value).lower() in ICMP_TYPE_MAP[self.protocol].values() else err_msg

class ICMPCodeValidator(Validator):
    """Validator for ICMP code. The value is number between 0 and 255
    """

    def __init__(self, protocol):
        """
        @param protocol: str
            The protocol for the ICMP type, either icmp or icmp6
        """
        self.suffix = "6" if protocol == 'icmp6' else ""

    def validate(self, value):
        err_msg = "Illegal ICMP%s code. It must be an integer between 0 and 255." % self.suffix
        try:
            n = int(value)
            return None if (n >= 0 and n <= 255) else err_msg
        except:
            return err_msg

class ICMPValidator(Validator):
    """Validator for ICMP parameters
    """

    def __init__(self, protocol, attribute_key = []):
        """
        @param protocol: str
            The protocol for the ICMP type, either icmp or icmp6
        @param attribute_key: str or list of str
            The key of a configuration attribute.
        """
        self.protocol = protocol
        self.attribute_key = [attribute_key] if isinstance(attribute_key, str) else attribute_key

    def validate(self, value):
        result = []
        kind = value.get('type')
        code = value.get('code')

        err_msg = ICMPTypeValidator(self.protocol).validate(kind)
        if err_msg:
            result.append(self.generate_fault(err_msg, self.attribute_key + ['type']))

        if not code:#code is optional
            return result
        err_msg = ICMPCodeValidator(self.protocol).validate(code)
        if err_msg:
            result.append(self.generate_fault(err_msg, self.attribute_key + ['code']))
        return result

class ProtocolValidator(Validator):
    """Validator for protocol type. The value is number between 0 and 255 , or a name in PROTOCOL_MAP
    """
    def validate(self, value):
        err_msg = "Illegal protocol type. It must be an integer between 0 and 255, or a protocol name."
        try:
            n = int(value)
            return None if (n >= 0 and n <= 255) else err_msg
        except:
            value = str(value).lower()
            return None if value in PROTOCOL_MAP.values() or PROTOCOL_MAP.has_key(value) else err_msg

class ServiceOperatorValidator(Validator):
    """Validator for service operator. The value is one of: 'lt', 'gt', 'eq', 'neq', or 'range'
    """
    def validate(self, value):
        err_msg = "Illegal service operator. It must be one of: 'lt', 'gt', 'eq', 'neq', or 'range'."
        if not str(value).lower() in ['lt', 'gt', 'eq', 'neq', 'range']:
            return err_msg


class ServicePortValidator(Validator):
    """Validator for port type. The value is number between 0 and 65536 , or a name in PORT_MAP
    """

    def __init__(self, protocol):
        """
        @param protocol: str
            the protocol for the port, either tcp or udp
        """
        self.protocol = protocol

    def validate(self, value):
        err_msg = "Illegal port type. It must be an integer between 0 and 255, or a port name."
        try:
            n = int(value)
            return None if (n >= 0 and n <= 65536) else err_msg
        except:
            value = str(value).lower()
            return None if value in PORT_MAP[self.protocol].values() or PORT_MAP[self.protocol].has_key(value) else err_msg

class TCPUDPValidator(Validator):
    'Validator for TCP/UDP service'

    def __init__(self, protocol, key_source="source", key_destination="destination"):
        """
        @param protocol: str
            the protocol for the port, either tcp, udp, or tcp-udp
        @param key_source: str
            the IFC key for the source folder in IFC configuration parameter
        @param key_destination: str
            the IFC key for the destination folder in IFC configuration parameter
        """
        self.protocol = protocol
        self.key_source = key_source
        self.key_destination = key_destination

    def validate(self, value):
        'Override default implementation to perform a concrete validation'
        def get_port_number(port):
            if port.isdigit():
                return int(port)
            if PORT_MAP[self.protocol].has_key(port):
                port = PORT_MAP[self.protocol][port]
            port = filter(lambda x: x[1] == port, PORT_MAP[self.protocol].items())[0][0]
            return int(port)

        result = []
        for name in [self.key_source, self.key_destination]:
            folder = value.get(name)
            if not folder:
                continue
            op = folder.get('operator')
            err_msg =  ServiceOperatorValidator().validate(op)
            if err_msg:
                result.append(self.generate_fault(err_msg, [name, 'operator']))

            lo_port = folder.get('low_port')
            err_msg = ServicePortValidator(self.protocol).validate(lo_port)
            if err_msg:
                result.append(self.generate_fault(err_msg, [name, 'low_port']))
                continue
            if 'range' != str(op).lower():
                continue

            hi_port = folder.get('high_port')
            if not hi_port:
                result.append(self.generate_fault("Missing value for high_port.", name))
                continue
            err_msg =  ServicePortValidator(self.protocol).validate(hi_port)
            if err_msg:
                result.append(self.generate_fault(err_msg, [name, 'high_port']))
            lo_port = get_port_number(lo_port)
            hi_port = get_port_number(hi_port)
            if lo_port > hi_port:
                result.append(self.generate_fault('low_port cannot be greater than high_port.', name))
        return result
