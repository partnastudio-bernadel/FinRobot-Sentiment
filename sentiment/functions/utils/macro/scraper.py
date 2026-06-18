import os
from playwright.sync_api import sync_playwright

def fetch_article_text(url: str, timeout_ms: int = 15000) -> str:
    """
    Fetches the raw webpage at the target URL using headless Playwright Chromium and extracts full paragraph text blocks.
    
    Use this tool ONLY when you need to load a raw news article URL in a headless browser and extract its full-text content.
    Do not use this tool for structured API endpoints or when a summary is already provided by the database.
    
    Args:
        url (str): The absolute URL of the news article page to scrape (e.g., 'https://finance.yahoo.com/news/...').
        timeout_ms (int): The loading and navigation timeout in milliseconds. Defaults to 15000.
        
    Returns:
        str: A single string containing all scraped article body paragraphs joined by double newlines. If scraping fails, returns an empty string.
        
    Example:
        fetch_article_text(url="https://finance.yahoo.com/news/example-article.html", timeout_ms=10000)
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            
            # Navigate and wait for DOM load
            page.goto(url, wait_until="domcontentloaded")
            
            # Wait for dynamic JS content to stabilize
            page.wait_for_timeout(2000)
            
            # Extract text from standard paragraph tags
            p_elements = page.query_selector_all("p")
            paragraphs = []
            for p_el in p_elements:
                try:
                    text = p_el.inner_text().strip()
                    if text and len(text) > 40:  # Avoid nav, footer, short phrases
                        paragraphs.append(text)
                except Exception:
                    continue
            
            context.close()
            browser.close()
            
            if paragraphs:
                return "\n\n".join(paragraphs)
            return ""
    except Exception as e:
        print(f"Scraper error for {url}: {e}")
        return ""
