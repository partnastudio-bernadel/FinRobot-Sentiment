def read_file_content(file_path):
    """Utility to read text from files (prompts, schemas, JSON mockups)."""
    with open(file_path, "r") as f:
        return f.read()

def extract_and_clean_response(user_proxy, agent, is_json=False):
    """Extracts the last message from an agent, strips TERMINATE, and cleans markdown JSON wraps."""
    msg = ""
    
    if is_json:
        # Search backward for the most recent message that contains a JSON object
        chat_history = user_proxy.chat_messages.get(agent, [])
        for message in reversed(chat_history):
            content = message.get("content", "")
            if isinstance(content, str) and "{" in content and "}" in content:
                msg = content
                break
        else:
            # Fallback to last message if no message containing braces is found
            last_msg_dict = user_proxy.last_message(agent)
            if last_msg_dict:
                msg = last_msg_dict.get("content", "") or ""
    else:
        last_msg_dict = user_proxy.last_message(agent)
        if last_msg_dict:
            msg = last_msg_dict.get("content", "") or ""

    if isinstance(msg, str):
        import re
        # Strip TERMINATE from beginning, end, or surrounded by whitespace
        msg = re.sub(r'^\s*TERMINATE\s*', '', msg, flags=re.IGNORECASE)
        msg = re.sub(r'\s*TERMINATE\s*$', '', msg, flags=re.IGNORECASE)
        msg = msg.strip()
        
    if is_json:
        if "```json" in msg:
            msg = msg.split("```json")[1].split("```")[0].strip()
        elif "```" in msg:
            msg = msg.split("```")[1].split("```")[0].strip()
            
        # Extract from the first '{' to the last '}' to strip unclosed blocks and trailing text (like TERMINATE)
        start_idx = msg.find('{')
        end_idx = msg.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            msg = msg[start_idx:end_idx+1].strip()
            
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