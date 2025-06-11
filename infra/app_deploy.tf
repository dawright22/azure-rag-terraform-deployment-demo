resource "kubernetes_namespace" "chatbot" {
  depends_on = [ module.aks.aks_name ]
  metadata {
    name = "chatbot"
  }
}

# Define the ServiceAccount
resource "kubernetes_service_account" "chatbot" {
  metadata {
    name      = "chatbot"
    namespace = kubernetes_namespace.chatbot.metadata[0].name
    annotations = {
      "azure.workload.identity/client-id" = azurerm_user_assigned_identity.chatbot.client_id
    }
    labels = {
      "azure.workload.identity/use" = "true"
    }
  }
}

# Define the ConfigMap for app code
resource "kubernetes_config_map" "app_code" {
  metadata {
    name      = "app-code"
    namespace = kubernetes_namespace.chatbot.metadata[0].name
  }

  data = {
    "app.py"           = file("../sample-application/chatbot.py")
    "requirements.txt" = file("../sample-application/requirements.txt")
  }
}

# Define the Pod
resource "kubernetes_pod" "chatbot" {
  metadata {
    name      = "chatbot"
    namespace = kubernetes_namespace.chatbot.metadata[0].name
    labels = {
      run = "chatbot"
      "azure.workload.identity/use" = "true"
    }
  }

  spec {
    service_account_name = kubernetes_service_account.chatbot.metadata[0].name

    container {
      name  = "chatbot"
      image = "ubuntu:20.04"
      
      env {
        name  = "VAULT_ADDR"
        value = var.vault_addr
      }
      env {
        name  = "VAULT_TOKEN"
        value = data.hcp_vault_secrets_secret.application_token.secret_value
      }
      env {
        name  = "VAULT_NAMESPACE"
        value = "admin"
      }
      env {
        name  = "AZURE_REGION"
        value = var.region
      }
      env {
        name  = "OPENAI_API_TYPE"
        value = var.openai_api_type
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = var.openai_api_version
      }
      env {
        name = "AZURE_OPENAI_ENDPOINT"
        value = module.openai.openai_endpoint
      }

      command = [
        "sh", "-c", <<-EOF
          echo "Updating and installing packages..." && \
          apt-get update && \
          apt-get install -y python3 python3-pip && \
          apt-get install -y libmagic1 && \
          echo "Creating directory structure..." && \
          mkdir -p /tmp/app/config && \
          pip install python-magic && \
          pip install requests && \
          pip install -U langchain-community && \
          pip install -U langchain-openai && \
          pip install hvac && \
          echo "Installing requirements..." && \
          pip3 install -r /app/requirements.txt && \
          pip install --upgrade langchain langchain-community openai pydantic && \
          echo "Starting application..." && \
          streamlit run /app/app.py
        EOF
      ]
      
      port {
        container_port = 8501
        protocol       = "TCP"
      }
      
      volume_mount {
        name      = "app-code"
        mount_path = "/app"
      }

    }

    volume {
      name = "app-code"
      config_map {
        name = kubernetes_config_map.app_code.metadata[0].name
      }
    }
  }
}

# Define the Service
resource "kubernetes_service" "chatbot" {
  metadata {
    name      = "chatbot"
    namespace = kubernetes_namespace.chatbot.metadata[0].name
  }

  spec {
    selector = {
      run = "chatbot"
    }

    port {
      port        = 80
      target_port = 8501
      protocol    = "TCP"
    }

    type = "LoadBalancer"
  }
}


