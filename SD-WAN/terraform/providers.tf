
provider "esxi" {
  esxi_username = var.esxi_username
  esxi_password = var.esxi_password
  esxi_hostname = var.esxi_hostname
}

provider "vsphere" {
  user           = var.vsphere_username
  password       = var.vsphere_password
  vsphere_server = var.vsphere_hostname

  # If you have a self-signed cert
  allow_unverified_ssl = true
}


data "vsphere_datacenter" "dc" {
  name = "CSH"
}

data "vsphere_datastore" "datastore" {
  name          = "ESX1_7TB_SSD_2xRAID0"
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_host" "host" {
  name          = "10.16.1.41"
  datacenter_id = "${data.vsphere_datacenter.dc.id}"
}

#resource "vsphere_resource_pool" "res_pool" {
#  name = "terraform-resource-pool-test"
#  parent_resource_pool_id = ""
#  cpu_limit = "2000"
#}