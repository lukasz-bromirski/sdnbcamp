import sys

if len(sys.argv) != 3:
    print ("""Usage:
    PODX_R1R2_template.py <pod_number> <router_number>
    
    ex. PODX_R1R2_template 5 2 (for POD5, router 2)""")
    exit(1)

pod = sys.argv[1]
router = sys.argv[2]

if ((int(pod) < 1) or (int(pod) >5)):
    print ("<pod_number> must be from 1 to 5")
    exit (1)

if ((int(router) < 1) or (int(router) >2)):
    print ("<router_number> must be either 1 or 2")
    exit (1)

print ("service timestamps debug datetime msec")
print ("service timestamps log datetime msec")

print ("hostname POD" + pod + "_R" + router)
print    
print ("enable password Admin" + pod + "sisko$")
print
print ("aaa new-model")
print
print ("ip domain name sda.lab")
print
print ("""archive 
 log config
  logging enable
  notify syslog contenttype plaintext""")
print
print("username cliadmin password 0 Admin" + pod + "sisko$")
print
print ("interface Loopback0")
print(" ip address 10.1" + pod + ".127.10" + router + " 255.255.255.255")
print (" ip pim sparse-mode")
print (" ip router isis") 
print
print ("interface GigabitEthernet0/0/0")
print (" no shutdown")
print
print ("interface GigabitEthernet0/0/1")
print (" dampening")
print (" no shutdown")
if (router == '1'):
    print (" ip address 10.1" + pod + ".80.3 255.255.255.254")
else:
    print (" ip address 10.1" + pod + ".80.5 255.255.255.254")
print (""" ip pim sparse-mode
 ip router isis 
 load-interval 30
 negotiation auto
 bfd interval 100 min_rx 100 multiplier 3
 no bfd echo
 clns mtu 1400
 isis network point-to-point 
""")

print ("router isis")
if (router == '1'):
    print (" net 49.0000.1111.1111.1111.00")
else:
    print (" net 49.0000.2222.2222.2222.00")
print (""" domain-password sisko
 metric-style wide
 log-adjacency-changes
 nsf ietf
 bfd all-interfaces
""")

print ("ip pim rp-address 10.1" + pod + ".66.1")
print ("ip pim register-source Loopback0")
print
print ("snmp-server community cisco RO")
print ("snmp-server community Admin" + pod + "sisko$ RW")
print 
   
