import os
import sys
import re
import base64
import logging
import hvac
import streamlit as st
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from azure.identity import ManagedIdentityCredential
from llama_index.core import (
    SimpleDirectoryReader,
    GPTVectorStoreIndex,
    PromptHelper,
    ServiceContext,
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.llms.langchain import LangChainLLM
from llama_index.embeddings.langchain import LangchainEmbedding
from dotenv import load_dotenv, dotenv_values

# Load environment variables from the mounted path
load_dotenv()

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger("llama_index").setLevel(logging.DEBUG)

index = None
doc_path = "./data/"
index_file = "index.json"

# Ensure the directory exists
if not os.path.exists(doc_path):
    os.makedirs(doc_path)  # Create the directory if it doesn't exist

# HashiCorp Vault configuration
vault_url = os.getenv('VAULT_ADDR')
vault_token = os.getenv('VAULT_TOKEN')
vault_namespace = os.getenv('VAULT_NAMESPACE')

client = hvac.Client(url=vault_url, token=vault_token, namespace=vault_namespace)

# Ensure the client is authenticated
if not client.is_authenticated():
    raise Exception("Vault authentication failed")

# Define regex patterns
regex_patterns = [
    r'AKIA[0-9A-Z]{16}',
    r'ASIA[0-9A-Z]{16}',
    r'[A-Za-z0-9/+=]{40}',
    r'(?<=")[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}(?=")'
]

if "config" not in st.session_state:
    # Read the environment variables
    config = {
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),  # Default API version
    }
    # Check if AZURE_CLIENT_ID env variable is set for Managed Identity
    if "AZURE_CLIENT_ID" in os.environ:
        credential = ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"])
        config["AZURE_OPENAI_API_KEY"] = credential.get_token("https://cognitiveservices.azure.com/.default").token
    else:
        logging.info("AZURE_CLIENT_ID not set, using AZURE_OPENAI_API_KEY from .env file")
    st.session_state.config = config

# Save current file name to avoid reprocessing document
if "current_file" not in st.session_state:
    st.session_state.current_file = None

def replace_matches_with_encryption(content):
    replacements = {}
    for pattern in regex_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if match not in replacements:
                encrypted_value = encrypt_with_vault(match)
                replacements[match] = encrypted_value
            content = content.replace(match, replacements[match])
    return content, replacements

def encrypt_with_vault(plain_text):
    plain_text_base64 = base64.b64encode(plain_text.encode('utf-8')).decode('utf-8')
    encryption_response = client.secrets.transit.encrypt_data(
        name='orders',
        plaintext=plain_text_base64
    )
    return encryption_response['data']['ciphertext']

def send_click():
    query_engine = index.as_query_engine()
    st.session_state.response = query_engine.query(st.session_state.prompt)

st.title("Azure OpenAI Doc Chatbot")

sidebar_placeholder = st.sidebar.container()

uploaded_file = st.file_uploader("Choose a file")

# Set context window
Settings.context_window = 4096

# Create the Azure OpenAI Chat LLM
try:
    llm = AzureChatOpenAI(
        deployment_name="gpt-35-turbo",
        azure_endpoint=st.session_state.config["AZURE_OPENAI_ENDPOINT"],
        openai_api_key=st.session_state.config["AZURE_OPENAI_API_KEY"],
        openai_api_version=st.session_state.config["AZURE_OPENAI_API_VERSION"]
    )
except Exception as e:
    logging.error(f"Error while initializing AzureChatOpenAI: {e}")
    raise

# Update Settings with AzureChatOpenAI instance
Settings.llm = llm

# Create the embedding LLM
try:
    embedding_llm = LangchainEmbedding(
        AzureOpenAIEmbeddings(
            model="text-embedding-ada-002",
            deployment="text-embedding-ada-002",  
            azure_endpoint=st.session_state.config["AZURE_OPENAI_ENDPOINT"],
            openai_api_key=st.session_state.config["AZURE_OPENAI_API_KEY"],
            openai_api_version=st.session_state.config["AZURE_OPENAI_API_VERSION"],
            chunk_size=1000  # Set chunk_size explicitly
        ),
        embed_batch_size=1,
    )
except Exception as e:
    logging.error(f"Error while initializing embedding model: {e}")
    raise

# Create llama_index LLMPredictor
llm_predictor = LangChainLLM(Settings.llm)
max_input_size = 4096
num_output = 256
max_chunk_overlap = 0.5
prompt_helper = PromptHelper(max_input_size, num_output, max_chunk_overlap)

# Create llama_index ServiceContext
service_context = ServiceContext.from_defaults(
    llm_predictor=llm_predictor,
    prompt_helper=prompt_helper,
    embed_model=embedding_llm,
    chunk_size_limit=1000,
)

if uploaded_file and uploaded_file.name != st.session_state.current_file:
    # Ingest the document and create the index
    with st.spinner('Ingesting the file...'):
        doc_files = os.listdir(doc_path)
        for doc_file in doc_files:
            os.remove(doc_path + doc_file)

        bytes_data = uploaded_file.read()
        content = bytes_data.decode('utf-8')
        updated_content, _ = replace_matches_with_encryption(content)
        with open(f"{doc_path}{uploaded_file.name}", "w") as f:
            f.write(updated_content)

        loader = SimpleDirectoryReader(doc_path, recursive=True, exclude_hidden=True)
        documents = loader.load_data()
        sidebar_placeholder.header("Current Processing Document:")
        sidebar_placeholder.subheader(uploaded_file.name)
        sidebar_placeholder.write(documents[0].get_text()[:500] + "...")

        index = GPTVectorStoreIndex.from_documents(
            documents, service_context=service_context
        )

        index.set_index_id("vector_index")
        index.storage_context.persist(index_file)
        st.session_state.current_file = uploaded_file.name
        st.session_state.response = ""  # Clean up the response when new file is uploaded
    st.success('Done!')

elif os.path.exists(index_file):
    # Read from storage context
    storage_context = StorageContext.from_defaults(persist_dir=index_file)
    index = load_index_from_storage(
        storage_context, index_id="vector_index", service_context=service_context
    )

    loader = SimpleDirectoryReader(doc_path, recursive=True, exclude_hidden=True)
    documents = loader.load_data()
    doc_filename = os.listdir(doc_path)[0]
    sidebar_placeholder.header("Current Processing Document:")
    sidebar_placeholder.subheader(doc_filename)
    sidebar_placeholder.write(documents[0].get_text()[:500] + "...")

if index:
    st.text_input("Ask something: ", key="prompt", on_change=send_click)
    st.button("Send", on_click=send_click)
    if st.session_state.response:
        st.subheader("Response: ")
        st.success(st.session_state.response, icon="🤖")
