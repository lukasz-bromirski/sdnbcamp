data "vsphere_datacenter" "datacenter" {
  name = "PODS"
}

data "vsphere_host" "esxi_host" {
  name          = var.esxi_hostname
  datacenter_id = data.vsphere_datacenter.datacenter.id
}

