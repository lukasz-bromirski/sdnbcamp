provider "esxi" {
  esxi_username = var.esxi_username
  esxi_password = var.esxi_password
  esxi_hostname = var.esxi_hostname

}


resource "esxi_guest" "leaf_switch" {

  for_each = {
    #          = "XN", X - pod number, N - LEAF11|LEAF12
    PODX_LEAF11 = "91"
    PODX_LEAF12 = "92"
  }

  disk_store = "datastore1"
  ovf_source  = format("/root/download/nexus/nx934_port_2%s1%s.ovf",substr(each.value,0,1), substr(each.value,1,1))
  guest_name = format("POD%s_LEAF1%s", substr(each.value,0,1),substr(each.value,1,1))

  power = "on"

  network_interfaces {
     # Mgmt0
     # SDN_PODX_VM
     virtual_network = format("SDN_POD%s_VM", substr(each.value,0,1))
     mac_address=format("02:00:fa:b%s:1%s:09", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/1
     # (2X11) PODX_LEAF1N_SPINE21
     virtual_network = format("(2%x1%s) POD%s_LEAF1%s_SPINE21", substr(each.value,0,1), 0+substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:1%s:11", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/2
     # (2X13) PODX_LEAF1N_SPINE22
     virtual_network = format("(2%x1%s) POD%s_LEAF1%s_SPINE22", substr(each.value,0,1), 2+substr(each.value,1,1), substr(each.value,0,1), substr(each.value,1,1))
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
    #          = "XN", X - pod number, N - SPINE21|SPINE22
    PODX_SPINE21 = "91"
    PODX_SPINE22 = "92"
  }

  disk_store = "datastore1"
  ovf_source  = format("/root/download/nexus/nx934_port_2%s2%s.ovf",substr(each.value,0,1), substr(each.value,1,1))
  guest_name = format("POD%s_SPINE2%s", substr(each.value,0,1),substr(each.value,1,1))

  power = "on"

  network_interfaces {
     # Mgmt0
     # SDN_PODX_VM
     virtual_network = format("SDN_POD%s_VM", substr(each.value,0,1))
     mac_address=format("02:00:fa:b%s:2%s:09", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/1
     # (2X11) PODX_LEAF11_SPINE2N
     virtual_network = format("(2%x1%s) POD%s_LEAF11_SPINE2%s", substr(each.value,0,1), (substr(each.value,1,1)-1)*2+1, substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:2%s:11", substr(each.value,0,1), substr(each.value,1,1))
  }
  network_interfaces {
     # Eth1/2
     # (2X13) PODX_LEAF12_SPINE2N
     virtual_network = format("(2%x1%s) POD%s_LEAF12_SPINE2%s", substr(each.value,0,1), (substr(each.value,1,1)-1)*2+2, substr(each.value,0,1), substr(each.value,1,1))
     mac_address=format("02:00:fa:b%s:2%s:12", substr(each.value,0,1), substr(each.value,1,1))
  }

}

