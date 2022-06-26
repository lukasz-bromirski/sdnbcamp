
# (2X11) PODX_LEAF11_SPINE21
# (2X12) PODX_LEAF12_SPINE21
# (2X13) PODX_LEAF11_SPINE22
# (2X14) PODX_LEAF12_SPINE22
# (2X23) PODX_LEAF11_EXT

resource "vsphere_host_port_group" "pod_portgroups" {

  for_each = var.portgroup_data

  name                = format("(2%s%s) POD%s_%s", var.pod, each.value["index"], var.pod, each.value["suffix"])
  host_system_id      = data.vsphere_host.esxi_host.id
  virtual_switch_name = "vSwitch0"

  vlan_id = format("2%s%s", var.pod, each.value["index"])

  allow_promiscuous = true
  allow_forged_transmits = true
  allow_mac_changes = true

}
