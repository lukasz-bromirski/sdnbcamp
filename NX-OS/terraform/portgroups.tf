provider "vsphere" {
  user           = var.vcsa_username
  password       = var.esxi_password
  vsphere_server = var.vcsa_hostname

  allow_unverified_ssl = true
}

data "vsphere_datacenter" "datacenter" {
  name = "SDN"
}

data "vsphere_host" "esxi_host" {
  name          = var.esxi_hostname
  datacenter_id = data.vsphere_datacenter.datacenter.id
}


resource "vsphere_host_port_group" "pod_portgroups" {

  for_each = {
    LEAF11_SPINE21 = "2911"
    LEAF11_SPINE22 = "2913"
    LEAF12_SPINE21 = "2912"
    LEAF12_SPINE22 = "2914"
    LEAF11_EXT     = "2923"
  }

  name                = format("(%s) POD%s_%s", each.value, substr(each.value,1,1), each.key)
  host_system_id      = data.vsphere_host.esxi_host.id
  virtual_switch_name = "vSwitch0"

  vlan_id = each.value

  allow_promiscuous = true
  allow_forged_transmits = true
  allow_mac_changes = true

}



