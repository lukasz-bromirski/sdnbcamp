'''
Created on Jan 28, 2013

@author: emilymw
Copyright (c) 2014 by Cisco Systems

'''
from state_type import State

class STSMap(object):
    '''
    This STSMap is an entry in STS table.  STSMap is a container class that collects a pair 
    of external and internal tag. The external and internal tag came from the VXLAN external 
    and internal interface's segment-id.  For example:
    interface vni               interface vni2
      segment-id 6000             segment-id 6001
      nameif FW1_external_Conn1   nameif FW1_external_Conn1
    
    This STSMap is collected during the ifc2asa() method.  Since we have to collect a pair
    but ifc2asa only handle one at a time. The design is to create an STSMap() key by firewall
    name and then store as either external or internal but depends on type.
    
    Unlike our DMObject, we do not create entries that are created during audit, instead we
    have to read the STS table from ASA and do a diff instead.  That's because it will always
    gaurantee that we are in sync with the STS table and can get back to a recoverable state.
    '''
    def __init__(self):
        self.add_external = None
        self.add_internal = None
        self.del_external = None
        self.del_internal = None
        self.no_change_external = None
        self.no_change_internal = None
        self.audit_state = State.CREATE

    def is_delete_needed(self):
        return self.del_external or self.del_internal

    def is_add_needed(self):
        return self.add_external or self.add_internal

    def is_no_change(self):
        return not self.add_external and not self.add_internal and \
            not self.del_external and not self.del_internal

    def is_not_audit_no_change(self):
        return self.audit_state != State.NOCHANGE
    
    def get_add(self):
        no_change = self.no_change_external if self.no_change_external else ' '
        add_ex = self.add_external if self.add_external else no_change
        no_change = self.no_change_internal if self.no_change_internal else ' '
        add_in = self.add_internal if self.add_internal else no_change
        return add_ex, add_in

    def get_delete(self):
        no_change = self.no_change_external if self.no_change_external else ' '
        del_ex = self.del_external if self.del_external else no_change
        no_change = self.no_change_internal if self.no_change_internal else ' '
        del_in = self.del_internal if self.del_internal else no_change
        return del_ex, del_in

    def gen_delete(self):
        return 'DEL,%s,%s\n' % (self.get_delete())

    def gen_add(self):
        return 'ADD,%s,%s\n' % (self.get_add())

    def gen_audit(self):
        if self.audit_state == State.CREATE:
            return self.gen_add()
        elif self.audit_state == State.DESTROY:
            return self.gen_delete()

    def is_exist(self, ex_tag, in_tag):
        if self.no_change_external == int(ex_tag) and self.no_change_internal == int(in_tag):
            return True
        add_ex, add_in = self.get_add()
        if add_ex == int(ex_tag) and add_in == int(in_tag):
            return True
        return False

    @staticmethod
    def set_sts_no_change(clss, fw_key, type_key, tag):
        sts_table = clss.get_top().sts_table
        if type_key == 'internal':
            sts_table[fw_key].no_change_internal = tag
        else:
            sts_table[fw_key].no_change_external = tag

    @staticmethod
    def set_sts_add(clss, fw_key, type_key, tag):
        sts_table = clss.get_top().sts_table
        if type_key == 'internal':
            sts_table[fw_key].add_internal = tag
        else:
            sts_table[fw_key].add_external = tag

    @staticmethod
    def set_sts_delete(clss, fw_key, type_key, tag):
        sts_table = clss.get_top().sts_table
        if type_key == 'internal':
            sts_table[fw_key].del_internal = tag
        else:
            sts_table[fw_key].del_external = tag

class STS(object):
    incr_parameter = \
            'DATABASE:STS_TABLE\n' \
            'DB_VERSION:1\n' \
            'DB_ACTION:INCR_UPDATE\n' \
            'BODY_TYPE:TABLE\n' \
            'COLS:3,STRING,UINT32,UINT32\n'
    audit_parameter = \
            'DATABASE:STS_TABLE\n' \
            'DB_VERSION:1\n' \
            'DB_ACTION:AUDIT\n' \
            'BODY_TYPE:NO_BODY\n' \
            'END\n'

    def __init__(self):
        self.sts_table = {}

    def diff_response(self, sts_input):
        '''
        This method is used during audit operation.  The result came from parsing the STS table
        query from ASA. In this case everything is ADD state from ASA.
        Example:  This are the lines and more like the CLI we read in from ASA.
          "ADD,6000,6001\n
           ADD,7000,7001\n"
        And we will loop through this line and compare to the sts_table that we collected
        so far from the ifc2asa() except ignoring the destroy generated by audit.
        '''
        lines = sts_input.split('\n')
        for map in lines:
            if not map:
                break
            op, ex_tag, in_tag = map.split(',')
            found = False
            for key, value in self.sts_table.iteritems():
                if value.is_exist(ex_tag, in_tag):
                    value.audit_state = State.NOCHANGE
                    found = True
                    break
            if not found:
                key = 'DEL_%s_%s' % (ex_tag, in_tag)
                self.sts_table[key] = STSMap()
                self.sts_table[key].del_external = ex_tag
                self.sts_table[key].del_internal = in_tag
                self.sts_table[key].audit_state = State.DESTROY

    def format_parameter(self, lines, count):
        parameters = self.incr_parameter
        parameters = parameters + 'ROWS:%s\n' % count
        parameters = parameters + lines
        parameters = parameters + 'END\n'
        return parameters

    def get_param(self):
        lines = ''
        count = 0
        for key, value in self.sts_table.iteritems():
            if value.is_delete_needed():
                del_string = value.gen_delete()
                if del_string:
                    lines = lines + del_string
                    count = count + 1
        for key, value in self.sts_table.iteritems():
            if value.is_add_needed():
                add_string = value.gen_add()
                if add_string:
                    lines = lines + add_string
                    count = count + 1
        if lines:
            return self.format_parameter(lines, count)
        else:
            return None

    def get_audit_param(self):
        lines = ''
        count = 0
        for key, value in self.sts_table.iteritems():
            if value.is_delete_needed() and value.is_not_audit_no_change():
                del_string = value.gen_delete()
                if del_string:
                    lines = lines + del_string
                    count = count + 1
        for key, value in self.sts_table.iteritems():
            if value.is_add_needed() and value.is_not_audit_no_change():
                add_string = value.gen_add()
                if add_string:
                    lines = lines + add_string
                    count = count + 1
        if lines:
            return self.format_parameter(lines, count)
        else:
            return None

    def parse_error(self, response):
        result = None
        message = ''
        if response:
            lines = response.split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':')
                    if 'DB_ACTION' == key and 'ERR' in value:
                        result = 'Failed: ' + value
                        return result
                else:
                    if line and line != 'END':
                        message= message + line + '\n'
        return message
