resource "azurerm_resource_group" "this" {
  location = var.region
  name     = random_pet.app_name[0].id
}