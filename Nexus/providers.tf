provider "vsphere" {
  user           = var.vcsa_username
  password       = var.vcsa_password
  vsphere_server = var.vcsa_hostname

  allow_unverified_ssl = true
}

