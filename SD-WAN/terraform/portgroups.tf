

resource "vsphere_host_port_group" "pod_portgroups" {

  for_each = {
    MPLS = "2531"
    INTERNET= "2532"
    CONTROLLERS= "2533"
    VE1_CORE= "2541"
    VE2_CORE= "2542"
    VE3_CORE= "2543"
    VE4_CORE= "2544"
    VE5_CORE= "2545"
  }

  name                = format("(%s) POD%s_SDWAN_%s", each.value, substr(each.value,1,1), each.key)
  host_system_id      = data.vsphere_host.host.id
  virtual_switch_name = "vSwitch0"

  vlan_id = each.value

  allow_promiscuous = true
  allow_forged_transmits = true
  allow_mac_changes = true

}



