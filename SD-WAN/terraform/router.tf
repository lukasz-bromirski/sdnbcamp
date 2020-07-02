

resource "esxi_guest" "podX_ve" {

  for_each = {
    POD5_VE1 = "51"
    POD5_VE2 = "52"
    POD5_VE3 = "53"
    POD5_VE4 = "54"
    POD5_VE5 = "55"
  }

  disk_store = "ESX1_7TB_SSD_2xRAID0"
  ovf_source  = format("/root/download/vEdge/%s.ovf",each.key)
  guest_name = format("SDWAN_%s", each.key)
  numvcpus = 2
  resource_pool_name = "testowa"

  power = "on"

  network_interfaces {
     # eth0
     nic_type = "vmxnet3"
     virtual_network = format("(31%s8) SDN_POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:aa:0%s:00:7%s", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # ge0/0
     nic_type = "vmxnet3"
     virtual_network = format("(2%s31) POD%s_SDWAN_MPLS", substr(each.value,0,1), substr(each.value,0,1))
  }
  network_interfaces {
     # ge0/1
     nic_type = "vmxnet3"
     virtual_network = format("(2%s32) POD%s_SDWAN_INTERNET", substr(each.value,0,1), substr(each.value,0,1))
  }
  network_interfaces {
     # ge0/2
     nic_type = "vmxnet3"
     virtual_network = format("(2%s33) POD%s_SDWAN_CONTROLLERS", substr(each.value,0,1), substr(each.value,0,1))
  }
}

