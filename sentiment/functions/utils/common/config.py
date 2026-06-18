def generate_config(model_name, api_endpoint, api_key, max_tokens=2048):
    """Generates the config list structure for FinRobot/AutoGen agents."""
    return [
        {
            "model": model_name,
            "base_url": api_endpoint,
            "api_key": api_key,
            "max_tokens": max_tokens
        }
    ]