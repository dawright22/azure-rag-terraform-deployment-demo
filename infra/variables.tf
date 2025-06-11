variable "region" {
  type    = string
  default = "eastus"
}

//vault address
variable "vault_addr" {
  type    = string
  default = "https://vault-public-vault-568210d2.b06d58cb.z1.hashicorp.cloud:8200"
}


//OPENAI_API_VERSION
variable "openai_api_version" {
  type    = string
  default = "2024-02-01"
}
//OPENAI_API_TYPE
variable "openai_api_type" {
  type    = string
  default = "azuread"
}

//hcp clinet id
variable "hcp_client_id" {
  type    = string
  default = "I8c8PxDiVoTGHpHDKXJZVFHCjw0rB5Tp"
}
//hcp client secret
variable "hcp_client_secret" {
  type    = string
  default = "QUjzPmmcGk-qW2BN0BoSPzS7Ki9xQ71UTv6znGV--3ir-dFxq305lSI-5jfAuxZT"
}
