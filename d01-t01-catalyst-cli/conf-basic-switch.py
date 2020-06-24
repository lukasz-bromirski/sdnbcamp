import csv
import re
import sys
from cli import configure, cli

# this script should be executed from IOS-XE guestshell

# it's quick & dirty implementation of parsing CSV files and
# configuring interfaces on Cisco Catalyst switches

if len(sys.argv) != 3:
    raise ValueError('Usage:\nconf-basic-switch.py input.csv device_name_to_match')

input_csv_filename = sys.argv[1]
input_device_name = sys.argv[2]

# get local (guestshell) hostname from device
tmp_name = cli("show running-config | i hostname")
local_switch_name = tmp_name.split(" ")

# main program loop that will parse line by line of CSV file
# and send configuration commands depending on contents
with open(input_csv_filename) as f:
    reader = csv.reader(f)
    for row in reader:
     if( row[0] == local_switch_name[1].rstrip() ):
      if ( row[2] == 'S' ):
         # switchport
         print ("Interface name: " + row[1] + " access VLAN: " + row[3])
         print(['- interface {}'.format(row[1]), 'switchport', 'switchport mode access', 'switchport access vlan {}'.format(row[3]), 'no shutdown'])
         configure(['vlan {}'.format(row[3]), 'name {}'.format(row[3])])
         configure(['interface {}'.format(row[1]), 'switchport', 'switchport mode access', 'switchport access vlan {} '.format(row[3]), 'no shutdown'])
      elif ( row[2] == 'L' ):
         # loopback
         print ("Interface name: " + row[1] + " IP address: " + row[3] + " netmask " + row[4])
         print(['- interface {}'.format(row[1]), 'ip address {} {}'.format(row[3],row [4]), 'no shutdown'])
         configure(['interface {}'.format(row[1]), 'ip address {} {}'.format(row[3],row[4]), 'no shutdown'])
      elif ( row[2] == 'I' ):
         # IP interface
         print ("Interface name: " + row[1] + " IP address: " + row[3] + " netmask " + row[4])
         print(['- interface {}'.format(row[1]), 'no switchport', 'ip address {} {}'.format(row[3],row [4]), 'no shutdown'])
         configure(['interface {}'.format(row[1]), 'no switchport', 'ip address {} {}'.format(row[3],row[4]), 'no shutdown'])
      elif ( row[2] == 'T' ):
         # trunk
         print ("Interface name: " + row[1] + " trunk" )
         print(['- interface {}'.format(row[1]), 'switchport', 'switchport mode trunk'])
         configure(['interface {}'.format(row[1]), 'switchport', 'switchport mode trunk'])
      else:
         print ("Unrecognized port type")
