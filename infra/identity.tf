# User Assigned Identity for Chatbot
resource azurerm_user_assigned_identity chatbot {
  name                = "chatbot"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
}

# Assign the "Cognitive Services User" to the chatbot User Assigned identity
resource "azurerm_role_assignment" "chatbot_role_assignment" {
  scope                = azurerm_resource_group.this.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.chatbot.principal_id
}

# Federated Identity Credential
resource "azurerm_federated_identity_credential" "chatbot_federated_identity" {
  name                = "chatbot-federated-identity"
  resource_group_name = azurerm_resource_group.this.name
  audience            = ["api://AzureADTokenExchange"]
  //issuer              = "https://eastus.oic.prod-aks.azure.com/237fbc04-c52a-458b-af97-eaf7157c0cd4/1e05d835-76b8-4170-8632-6eaf61fe286c/"
  issuer              = module.aks.oidc_issuer_url 
  parent_id           = azurerm_user_assigned_identity.chatbot.id
  subject             = "system:serviceaccount:${kubernetes_namespace.chatbot.metadata[0].name}:${kubernetes_service_account.chatbot.metadata[0].name}"
}


