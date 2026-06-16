from autogen import initiate_chats

def custom_nested_chat_reply(chat_queue, recipient, messages, sender, config):
    """Custom reply handler for AutoGen nested chats.
    
    This function:
    1. Executes the sub-agents nested chat queue (scoring step).
    2. Extracts the Scorer's final output summary (JSON scored articles).
    3. Injects the summary directly into the CIO Agent's main chat history.
    4. Returns (False, None) to prevent the built-in handler from directly 
       replying to the user, allowing the CIO Agent to run its own LLM 
       consolidator logic on the scoring summary.
    """
    # Guard: prevent scoring triggered with empty/blank articles input
    last_msg = messages[-1].get("content", "").strip() if messages else ""
    if not last_msg or last_msg == "[]":
        return True, "No articles provided to score. TERMINATE"

    chats_to_run = recipient._get_chats_to_run(chat_queue, recipient, messages, sender, config)
    if not chats_to_run:
        return True, None
    
    res = initiate_chats(chats_to_run)
    scorer_summary = res[-1].summary
    
    # Append the Scorer's scored articles JSON directly to the CIO Agent's history
    recipient.send(
        message=scorer_summary,
        recipient=sender,
        request_reply=False,
        silent=True
    )
    
    # Return (False, None) so the CIO Agent executes its own LLM text generation next
    return False, None
