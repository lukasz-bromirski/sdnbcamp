
data "vsphere_resource_pool" "pool" {
  #name          = format("pod%s", var.pod)
  name = format("pod%s_evpn", var.pod)
  datacenter_id = data.vsphere_datacenter.datacenter.id
}

data "vsphere_datastore" "datastore" {
  name          = format("pod%s-esx2-ds1", var.pod)
  datacenter_id = data.vsphere_datacenter.datacenter.id
}

data "vsphere_virtual_machine" "template" {
  name          = format("pod%s_n9300v", var.pod)
  datacenter_id = data.vsphere_datacenter.datacenter.id
}

data "vsphere_network" "net_mgmt" {
  name          = format("(31%s8) SDN_POD%s_VM", var.pod, var.pod)
  datacenter_id = data.vsphere_datacenter.datacenter.id
}



