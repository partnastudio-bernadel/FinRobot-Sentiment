def read_file_content(file_path):
    """Utility to read text from files (prompts, schemas, JSON mockups)."""
    with open(file_path, "r") as f:
        return f.read()

def extract_and_clean_response(user_proxy, agent, is_json=False):
    """Extracts the last message from an agent, strips TERMINATE, and cleans markdown JSON wraps."""
    msg = user_proxy.last_message(agent).get("content", "")
    if msg.endswith("TERMINATE"):
        msg = msg[:-9].strip()
        
    if is_json:
        if "```json" in msg:
            msg = msg.split("```json")[1].split("```")[0].strip()
        elif "```" in msg:
            msg = msg.split("```")[1].split("```")[0].strip()
            
    return msg

def strip_name_hook(messages):
    """Strips the 'name' parameter from AutoGen message payloads to satisfy strict client API constraints (e.g. NVIDIA NIM)."""
    cleaned = []
    for msg in messages:
        c_msg = msg.copy()
        if "name" in c_msg:
            del c_msg["name"]
        cleaned.append(c_msg)
    return cleaned