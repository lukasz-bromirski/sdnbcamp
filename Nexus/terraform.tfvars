vcsa_hostname = "vcenter.sdn.lab"
vcsa_username = "podX-admin@hector.lan"
esxi_hostname = "podX-esx2.sdn.lab"

pod = X

portgroup_data = {
  PG11 = {
    index = 11
    suffix = "LEAF11_SPINE21"
  }
  PG12 = {
    index = 12
    suffix = "LEAF12_SPINE21"
  }
  PG13 = {
    index = 13
    suffix = "LEAF11_SPINE22"
  }
  PG14 = {
    index = 14
    suffix = "LEAF12_SPINE22"
  }
  PG23 = {
    index = 23
    suffix = "LEAF11_EXT"
  }
}

leaf1_data = {
  LEAF11 = {
    name = "PODX_LEAF11"
    portgroup_index = 1
    serial_port = 2X11
    mgmt = 10
    eth1 = 11
    eth2 = 12
    eth3 = 13
    eth4 = 14
  }
}

leaf2_data = {
  LEAF12 = {
    name = "PODX_LEAF12"
    portgroup_index = 2
    serial_port = 2X12
    mgmt = 10
    eth1 = 11
    eth2 = 12
    eth3 = 13
  }
}

spine1_data = {
  SPINE21 = {
    name = "PODX_SPINE21"
    portgroup_index = 1
    serial_port = 2X21
    mgmt = 10
    eth1 = 11
    eth2 = 12
  }
}

spine2_data = {
  SPINE22 = {
    name = "PODX_SPINE22"
    portgroup_index = 2
    serial_port = 2X22
    mgmt = 10
    eth1 = 11
    eth2 = 12
  }
}