import json
from autogen import initiate_chats

def extract_json_array(text):
    """Extracts a JSON list or dict from a string, supporting markdown wraps."""
    if not text:
        return None
    text_stripped = text.strip()
    try:
        return json.loads(text_stripped)
    except Exception:
        pass
    
    # Try finding bounding brackets
    start_list = text.find('[')
    end_list = text.rfind(']')
    start_dict = text.find('{')
    end_dict = text.rfind('}')
    
    # Pick whichever JSON bounding box is outermost
    start = -1
    end = -1
    if start_list != -1 and end_list != -1:
        start = start_list
        end = end_list
    if start_dict != -1 and end_dict != -1:
        if start == -1 or start_dict < start:
            start = start_dict
            end = end_dict
            
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
            
    return None

def merge_scored_results(batch_results):
    """Merges multiple scored batch responses from the Scorer Agent.
    
    Supports merging both list-of-ticker-dicts and single-ticker-dict output structures.
    """
    merged_map = {}
    for result in batch_results:
        items = []
        if isinstance(result, dict):
            items = [result]
        elif isinstance(result, list):
            items = result
        else:
            continue
            
        for item in items:
            if not isinstance(item, dict):
                continue
            ticker = item.get("ticker")
            if not ticker:
                continue
            
            articles = item.get("articles", [])
            if not isinstance(articles, list):
                articles = []
                
            if ticker not in merged_map:
                merged_map[ticker] = {
                    "ticker": ticker,
                    "metadata": {
                        "timestamp": item.get("metadata", {}).get("timestamp", ""),
                        "article_count": 0
                    },
                    "articles": []
                }
            
            merged_map[ticker]["articles"].extend(articles)
            
    for ticker, entry in merged_map.items():
        entry["metadata"]["article_count"] = len(entry["articles"])
        
    if len(merged_map) == 1:
        return list(merged_map.values())[0]
    return list(merged_map.values())

def custom_nested_chat_reply(chat_queue, recipient, messages, sender, config):
    """Custom reply handler for AutoGen nested chats.
    
    This function:
    1. Extracts the raw articles list from the User Proxy's initiation message.
    2. Batches the scoring pipeline into cycles of 5 to prevent LLM output token limits from truncating responses.
    3. Runs the nested chats queue sequentially for each batch.
    4. Merges all scored articles and injects the summary back to the CIO Agent.
    5. Returns (False, None) to let the CIO Agent run its consolidation LLM logic.
    """
    # Guard: prevent scoring triggered with empty/blank articles input
    last_msg = messages[-1].get("content", "").strip() if messages else ""
    if not last_msg or last_msg == "[]":
        return True, "No articles provided to score. TERMINATE"

    # Parse raw articles list from incoming message
    articles_list = extract_json_array(last_msg)

    # Fallback to standard non-batched run if articles cannot be parsed as a list
    if not articles_list or not isinstance(articles_list, list):
        chats_to_run = recipient._get_chats_to_run(chat_queue, recipient, messages, sender, config)
        if not chats_to_run:
            return True, None
        res = initiate_chats(chats_to_run)
        scorer_summary = res[-1].summary
    else:
        # Transparent batching in cycles of 5
        batch_size = 5
        batch_results = []
        
        for i in range(0, len(articles_list), batch_size):
            batch = articles_list[i:i + batch_size]
            print(f"[*] Batching scoring pipeline: processing articles {i+1} to {min(i+batch_size, len(articles_list))} of {len(articles_list)}")
            
            # Create a copy of the chat queue overriding the message lambda with only the current batch
            temp_chat_queue = []
            for chat_config in chat_queue:
                temp_config = chat_config.copy()
                temp_config["message"] = (
                    "Please score the following articles according to your instructions:\n\n"
                    f"{json.dumps(batch, indent=2)}\n\n"
                    "Respond with the list of scored articles."
                )
                temp_chat_queue.append(temp_config)
                
            chats_to_run = recipient._get_chats_to_run(temp_chat_queue, recipient, messages, sender, config)
            res = initiate_chats(chats_to_run)
            
            # Extract scored results
            summary_content = res[-1].summary
            scored_data = extract_json_array(summary_content)
            if scored_data is not None:
                batch_results.append(scored_data)
            else:
                try:
                    clean_content = summary_content
                    if clean_content.endswith("TERMINATE"):
                        clean_content = clean_content[:-9].strip()
                    batch_results.append(json.loads(clean_content))
                except Exception:
                    pass
                    
        # Merge batch results
        merged_result = merge_scored_results(batch_results)
        scorer_summary = json.dumps(merged_result, indent=2)
    
    # Append the Scorer's scored articles JSON directly to the CIO Agent's history
    recipient.send(
        message=scorer_summary,
        recipient=sender,
        request_reply=False,
        silent=True
    )
    
    # Return (False, None) so the CIO Agent executes its own LLM text generation next
    return False, None

