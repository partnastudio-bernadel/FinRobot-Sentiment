import sys
import os
from dotenv import load_dotenv
from functions.utils.common.config import generate_config

# Ensure the sentiment folder is in python path for importing modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sentiment_dir = os.path.dirname(current_dir)
if sentiment_dir not in sys.path:
    sys.path.insert(0, sentiment_dir)

# Load environment variables from .env.local in sentiment directory
env_path = os.path.join(sentiment_dir, ".env.local")
load_dotenv(env_path)

nvidia_base_model = os.getenv("NVIDIA_TOOLING_MODEL", "").strip('"\' ')
nvidia_tooling_model = os.getenv("NVIDIA_BASE_MODEL_ALT", "meta/llama-3.1-8b-instruct").strip('"\' ')
nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\' ')
nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\' ')

hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "").strip('"\' ')
hf_model_name = os.getenv("HUGGINGFACE_MODEL_NAME_FEATHERLESS", "curiousily/Llama-3-8B-Instruct-Finance-RAG").strip('"\' ')
hf_base_url = os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1").strip('"\' ')

config_list = generate_config(hf_model_name, hf_base_url, hf_api_key)
base_config_list = generate_config(nvidia_base_model, nvidia_api_endpoint, nvidia_api_key)
tooling_config_list = generate_config(nvidia_tooling_model, nvidia_api_endpoint, nvidia_api_key)

llm_config = {"config_list": config_list, "model": hf_model_name}
base_llm_config = {"config_list": base_config_list, "model": nvidia_base_model}
tooling_llm_config = {"config_list": tooling_config_list, "model": nvidia_tooling_model}
