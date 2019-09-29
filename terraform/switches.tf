provider "esxi" {
  esxi_username = "${var.esxi_username}"
  esxi_password = "${var.esxi_password}"
  esxi_hostname = "${var.esxi_hostname}"

}


resource "esxi_guest" "leaf_switch" {

  for_each = {
    #          = "XN", X - pod number, N - LEAF11|LEAF12
    PODX_LEAF11 = "11"
    PODX_LEAF12 = "12"
  }

  disk_store = "1.3T_SSD"
  ovf_source  = format("/root/download/nx932_port_23%s.ovf",each.value)
  guest_name = format("POD%s_LEAF1%s", substr(each.value,0,1),substr(each.value,1,1))

  power = "on"

  network_interfaces {
     # Mgmt0
     # (3X18) PODX_VM
     virtual_network = format("(3%s18) POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:fa:b%s:1%s:09", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/1
     # (2X11) PODX_LEAF1N_SPINE11
     virtual_network = format("(2%x1%s) POD%s_LEAF1%s_SPINE11", substr(each.value,0,1), 0+substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:1%s:11", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/2
     # (2X13) PODX_LEAF1N_SPINE12
     virtual_network = format("(2%x1%s) POD%s_LEAF1%s_SPINE12", substr(each.value,0,1), 2+substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:1%s:12", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/3
     # (2X2N) PODX_LEAF1N_SRV1N
     virtual_network = format("(2%x2%s) POD%s_LEAF1%s_SRV1%s", substr(each.value,0,1), substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:1%s:13", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/4
     # (2X23) PODX_VXLAN_CORE
     # (2X22+N) PODX_LEAF1N_EXT
     virtual_network = format("(2%x2%s) POD%s_LEAF1%s_EXT", substr(each.value,0,1),2+substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:1%s:14", substr(each.value,0,1), substr(each.value,1,1))
  }

}


resource "esxi_guest" "spine_switch" {

  for_each = {
    #          = "XN", X - pod number, N - SPINE11|SPINE12
    PODX_SPINE11 = "11"
    PODX_SPINE12 = "12"
  }

  disk_store = "1.3T_SSD"
  ovf_source  = format("/root/download/nx932_port_23%s.ovf",each.value+2)
  guest_name = format("POD%s_SPINE1%s", substr(each.value,0,1),substr(each.value,1,1))

  power = "on"

  network_interfaces {
     # Mgmt0
     # (3X18) PODX_VM
     virtual_network = format("(3%s18) POD%s_VM", substr(each.value,0,1), substr(each.value,0,1))
     mac_address=format("02:00:fa:b%s:2%s:09", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/1
     # (2X11) PODX_LEAF11_SPINE1N
     virtual_network = format("(2%x1%s) POD%s_LEAF11_SPINE1%s", substr(each.value,0,1), (substr(each.value,1,1)-1)*2+1, substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:2%s:11", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/2
     # (2X13) PODX_LEAF12_SPINE1N
     virtual_network = format("(2%x1%s) POD%s_LEAF12_SPINE1%s", substr(each.value,0,1), (substr(each.value,1,1)-1)*2+2, substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:2%s:12", substr(each.value,0,1), substr(each.value,1,1))
  }

}

