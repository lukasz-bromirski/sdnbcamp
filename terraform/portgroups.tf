provider "vsphere" {
  user           = "${var.esxi_username}"
  password       = "${var.esxi_password}"
  vsphere_server = "${var.esxi_hostname}"

  allow_unverified_ssl = true
}

data "vsphere_datacenter" "datacenter" {
  name = "dc1"
}

data "vsphere_host" "esxi_host" {
  name          = "esxi1"
  datacenter_id = "${data.vsphere_datacenter.datacenter.id}"
}


resource "vsphere_host_port_group" "pod_portgroups" {

  for_each = {
    LEAF11_SPINE11 = "2111"
    LEAF11_SPINE12 = "2113"
    LEAF12_SPINE11 = "2112"
    LEAF12_SPINE12 = "2114"
    LEAF11_EXT = "2123"
  }

  name                = format("(%s) POD%s_%s", each.value, substr(each.value,1,1), each.key)
  host_system_id      = "${data.vsphere_host.esxi_host.id}"
  virtual_switch_name = "vSwitch0"

  vlan_id = each.value

  allow_promiscuous = true
  allow_forged_transmits = true
  allow_mac_changes = true

}



