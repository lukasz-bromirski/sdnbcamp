import sys

if len(sys.argv) != 2:
    print ("""Usage:
    PODX_R1R2_SW3_config.py <pod_number> 
    
    ex. PODX_R1R2_config 5 (for POD5)""")
    exit(1)

pod = sys.argv[1]

if ((int(pod) < 1) or (int(pod) >5)):
    print ("<pod_number> must be from 1 to 5")
    exit (1)


print("""interface Gi1/0/23 
 description Fabric Physical Link
 no switchport
 dampening
 ip address 10.1""" + pod + """.80.2 255.255.255.254
 ip lisp source-locator Loopback0
 ip pim sparse-mode
 ip router isis 
 load-interval 30
 bfd interval 100 min_rx 100 multiplier 3
 no bfd echo
 clns mtu 1400
 isis network point-to-point""") 
print
print("""interface Gi1/0/24 
 description Fabric Physical Link
 no switchport
 dampening
 ip address 10.1""" + pod + """.80.4 255.255.255.254
 ip lisp source-locator Loopback0
 ip pim sparse-mode
 ip router isis 
 load-interval 30
 bfd interval 100 min_rx 100 multiplier 3
 no bfd echo
 clns mtu 1400
 isis network point-to-point""") 
