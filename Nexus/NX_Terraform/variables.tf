variable "vcsa_hostname" {
}

variable "esxi_hostname" {
}

variable "vcsa_username" {
}

variable "vcsa_password" {
}

variable "pod" {
}

variable "portgroup_data" {
  type = map(object({
    index = number
    suffix = string
  }))
}

variable "leaf1_data" {
  type = map(object({
    name = string
    portgroup_index = number
    serial_port = number
    mgmt = number
    eth1 = number
    eth2 = number
    eth3 = number
    eth4 = number
  }))
}

variable "leaf2_data" {
  type = map(object({
    name = string
    portgroup_index = number
    serial_port = number
    mgmt = number
    eth1 = number
    eth2 = number
    eth3 = number
  }))
}

variable "spine1_data" {
  type = map(object({
    name = string
    portgroup_index = number
    serial_port = number
    mgmt = number
    eth1 = number
    eth2 = number
  }))
}

variable "spine2_data" {
  type = map(object({
    name = string
    portgroup_index = number
    serial_port = number
    mgmt = number
    eth1 = number
    eth2 = number
  }))
}