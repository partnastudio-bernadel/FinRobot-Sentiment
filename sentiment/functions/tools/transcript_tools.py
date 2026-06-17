import os
import requests

def fetch_and_split_transcript(ticker: str, year: int = None, quarter: int = None) -> dict:
    """Retrieves the earnings call transcript from FMP and splits it into Presentation and Q&A blocks.
    
    Args:
        ticker (str): Stock ticker symbol (e.g. 'AAPL').
        year (int, optional): Fiscal year of the transcript. Defaults to None (gets latest).
        quarter (int, optional): Fiscal quarter (1, 2, 3, or 4). Defaults to None (gets latest).
        
    Returns:
        dict: A dictionary containing:
            - 'presentation' (str): The corporate presentation block.
            - 'qa' (str): The analyst Q&A block.
            - 'meta' (dict): Metadata containing date, quarter, year, and symbol.
    """
    api_key = os.getenv("FMP_API_KEY", "").strip('"\'')
    if not api_key:
        raise ValueError("FMP_API_KEY is not configured in environment.")

    ticker = ticker.upper().strip()
    
    # Build the URL. FMP supports querying by quarter and year.
    # If not provided, we query without them to get the latest transcripts.
    if year and quarter:
        url = f"https://financialmodelingprep.com/api/v3/earnings_call_transcript/{ticker}?quarter={quarter}&year={year}&apikey={api_key}"
        print(f"[*] Fetching transcript for {ticker} Q{quarter} {year} via FMP API...")
    else:
        url = f"https://financialmodelingprep.com/api/v3/earnings_call_transcript/{ticker}?apikey={api_key}"
        print(f"[*] Fetching latest transcripts for {ticker} via FMP API...")
        
    res = requests.get(url)
    res.raise_for_status()
    data = res.json()
    
    if not data or not isinstance(data, list):
        # Fallback payload to prevent upstream failures
        print(f"[!] Warning: no transcript data returned for {ticker}.")
        return {
            "presentation": "No transcript available.",
            "qa": "No Q&A section available.",
            "meta": {"symbol": ticker, "quarter": quarter or 0, "year": year or 0, "date": "unknown"}
        }
        
    # Get the latest entry in the list
    transcript_entry = data[0]
    content = transcript_entry.get("content", "")
    
    # Split the transcript
    presentation, qa = split_transcript(content)
    
    print(f"[*] Successfully retrieved and split transcript for {ticker} (Presentation length: {len(presentation)} chars, Q&A length: {len(qa)} chars).")
    
    return {
        "presentation": presentation,
        "qa": qa,
        "meta": {
            "symbol": transcript_entry.get("symbol", ticker),
            "quarter": transcript_entry.get("quarter", 0),
            "year": transcript_entry.get("year", 0),
            "date": transcript_entry.get("date", "unknown")
        }
    }

def split_transcript(content: str) -> tuple[str, str]:
    """Isolates the corporate Management Presentation from the Analyst Q&A block."""
    if not content:
        return "", ""
        
    # Standard headers used in transcripts to signal transition to Q&A
    qa_headers = [
        "question-and-answer session",
        "question and answer session",
        "questions and answers",
        "q & a session",
        "q&a session",
        "q&a",
        "questions and answer"
    ]
    
    content_lower = content.lower()
    for header in qa_headers:
        idx = content_lower.find(header)
        if idx != -1:
            presentation = content[:idx].strip()
            # Retain the header in the Q&A block for context
            qa = content[idx:].strip()
            return presentation, qa
            
    # If no Q&A block separator is found, return the first half as presentation and second half as Q&A
    print("[!] Warning: Q&A transition header not found. Splitting transcript by length.")
    half_len = len(content) // 2
    return content[:half_len].strip(), content[half_len:].strip()
