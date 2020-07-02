
resource "esxi_guest" "vBond" {

  for_each = {
    POD5_vBond1 = "51"
  }

  disk_store = "ESX1_7TB_SSD_2xRAID0"
  ovf_source  = format("/root/download/vEdge/%s.ovf",each.key)
  guest_name = format("SDWAN_%s", each.key)
  numvcpus = 2

  power = "on"

  network_interfaces {
     # eth0
     nic_type = "vmxnet3"
     virtual_network = format("(31%s8) SDN_POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:aa:0%s:00:71", substr(each.value,0,1))
  }
  network_interfaces {
     # ge0/0
     nic_type = "vmxnet3"
     virtual_network = format("(2%s33) POD%s_SDWAN_CONTROLLERS", substr(each.value,0,1), substr(each.value,0,1))
  }
}

resource "esxi_guest" "vSmart" {

  for_each = {
    POD5_vSmart1 = "51"
  }

  disk_store = "ESX1_7TB_SSD_2xRAID0"
  ovf_source  = format("/root/download/vSmart/%s.ovf",each.key)
  guest_name = format("SDWAN_%s", each.key)
  numvcpus = 2

  power = "on"

  network_interfaces {
     # eth0
     nic_type = "vmxnet3"
     virtual_network = format("(31%s8) SDN_POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:aa:0%s:00:73", substr(each.value,0,1))
  }
  network_interfaces {
     # eth1
     nic_type = "vmxnet3"
     virtual_network = format("(2%s33) POD%s_SDWAN_CONTROLLERS", substr(each.value,0,1), substr(each.value,0,1))
  }
}

#resource "esxi_resource_pool" "vm_res1" {
#  resource_pool_name = "vmres1"
#  cpu_max = "2000"
#}

resource "esxi_virtual_disk" "vmanage_disk" {

  virtual_disk_disk_store = "ESX1_7TB_SSD_2xRAID0"
  virtual_disk_dir = "SDWAN_vManage_datadisks"
  virtual_disk_name = "POD5_vManage.vmdk"
  virtual_disk_size = "100"
}


resource "esxi_guest" "vManage" {

  for_each = {
    POD5_vManage1 = "51"
  }

  disk_store = "ESX1_7TB_SSD_2xRAID0"
  ovf_source  = format("/root/download/vManage/%s.ovf",each.key)
  guest_name = format("SDWAN_%s", each.key)
  numvcpus = 2

  power = "off"

  #resource_pool_name = "vmres1"

  virtual_disks {
    virtual_disk_id = esxi_virtual_disk.vmanage_disk.id
    slot = "0:1"
  }

  network_interfaces {
     # eth0
     nic_type = "vmxnet3"
     virtual_network = format("(31%s8) SDN_POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:aa:0%s:00:72", substr(each.value,0,1))
  }
  network_interfaces {
     # eth1
     nic_type = "vmxnet3"
     virtual_network = format("(2%s33) POD%s_SDWAN_CONTROLLERS", substr(each.value,0,1), substr(each.value,0,1))
  }
}


