data "hcp_vault_secrets_secret" "application_token" {
  app_name = "sample-app"
  secret_name = "kube_app"
}