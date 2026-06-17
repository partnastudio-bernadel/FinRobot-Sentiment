from typing import Dict, List, Tuple, Optional, Any

def calculate_raw_sentiment(articles: List[Dict[str, Any]]) -> float:
    """Calculates the confidence-weighted average sentiment score of scored articles.
    
    Formula:
        S_raw = sum(s_i * c_i) / sum(c_i)
        
    Args:
        articles: A list of dicts containing 'sentiment_score' (float) and 'confidence' (float).
        
    Returns:
        The raw sentiment score in range [-1.0, 1.0], defaulting to 0.0 if empty or zero confidence.
    """
    if not articles:
        return 0.0
        
    weighted_sum = 0.0
    confidence_sum = 0.0
    
    for article in articles:
        score = article.get("sentiment_score", 0.0)
        confidence = article.get("confidence", 0.0)
        
        # Guard against malformed or missing values
        if score is None or confidence is None:
            continue
            
        weighted_sum += score * confidence
        confidence_sum += confidence
        
    if confidence_sum == 0.0:
        return 0.0
        
    return weighted_sum / confidence_sum


def calculate_macro_surprise(
    actual: float, 
    consensus: float, 
    historical_std: float, 
    tier: str
) -> Tuple[float, bool]:
    """Computes macroeconomic surprise metrics.
    
    Formula:
        S_t = omega_static * | (Actual_t - Consensus_t) / sigma_historical |
        
    Args:
        actual: The released economic value.
        consensus: The forecast consensus value.
        historical_std: The rolling historical standard deviation (sigma_historical).
        tier: Event tier category ('red', 'orange', 'yellow').
        
    Returns:
        A tuple of (surprise_index, warning_flag).
        warning_flag is True if historical_std was invalid (<= 0 or None) and standard fallback of 1.0 was used.
    """
    # Event tier static weights (supports color codes or priority strings)
    tier_weights = {
        "red": 1.0,
        "high": 1.0,
        "orange": 0.5,
        "medium": 0.5,
        "yellow": 0.2,
        "low": 0.2
    }
    
    omega = tier_weights.get(tier.lower(), 0.2)
    warning_flag = False
    
    # Handle invalid or division-by-zero cases
    if historical_std is None or historical_std <= 0.0:
        std_denominator = 1.0
        warning_flag = True
    else:
        std_denominator = historical_std
        
    surprise_index = omega * abs((actual - consensus) / std_denominator)
    return surprise_index, warning_flag


def calculate_effective_sentiment(
    ticker: str, 
    raw_sentiment: float, 
    macro_shock: float, 
    custom_beta: Optional[float] = None
) -> float:
    """Calculates Effective Ticker Sentiment incorporating macro surprise scaled by sector sensitivity.
    
    Formula:
        Effective Sentiment = raw_sentiment * (1 + beta_j * macro_shock)
        
    Args:
        ticker: The asset stock ticker symbol (e.g. 'AAPL').
        raw_sentiment: Confidence-weighted raw sentiment score (S_raw).
        macro_shock: The calculated macro shock index (S_t).
        custom_beta: Optional beta coefficient. If not passed, defaults to fallback.
        
    Returns:
        The adjusted effective sentiment score.
    """
    # Fallback lookup dictionary for sector sensitivity beta defaults
    DEFAULT_BETAS = {
        "AAPL": 1.2,
        "MSFT": 1.1,
        "QQQ": 1.0
    }
    
    beta = custom_beta if custom_beta is not None else DEFAULT_BETAS.get(ticker.upper(), 1.0)
    
    return raw_sentiment * (1.0 + beta * macro_shock)


def calculate_portfolio_sentiment(
    weights: Dict[str, float], 
    effective_sentiments: Dict[str, float]
) -> float:
    """Aggregates effective ticker sentiments by portfolio holding weight.
    
    Formula:
        S_portfolio = sum(w_j * Effective_Sentiment_j)
        
    Args:
        weights: Dictionary mapping tickers to portfolio weights (e.g., {'AAPL': 0.4}).
        effective_sentiments: Dictionary mapping tickers to their effective sentiments.
        
    Returns:
        The portfolio-weighted sentiment exposure value.
    """
    if not weights or not effective_sentiments:
        return 0.0
        
    total_exposure = 0.0
    
    for ticker, weight in weights.items():
        sentiment = effective_sentiments.get(ticker, 0.0)
        total_exposure += weight * sentiment
        
    return total_exposure


def calculate_portfolio_drift(
    actual_weights: Dict[str, float], 
    target_weights: Dict[str, float]
) -> float:
    """Calculates active portfolio drift using the L1-norm deviation.
    
    Formula:
        Drift = sum( |w_actual_j - w_target_j| )
        
    Args:
        actual_weights: Dictionary mapping tickers to current actual portfolio weights.
        target_weights: Dictionary mapping tickers to strategic target weights.
        
    Returns:
        The drift distance value (0.0 to 2.0).
    """
    all_tickers = set(actual_weights.keys()).union(set(target_weights.keys()))
    total_drift = 0.0
    
    for ticker in all_tickers:
        actual_w = actual_weights.get(ticker, 0.0)
        target_w = target_weights.get(ticker, 0.0)
        total_drift += abs(actual_w - target_w)
        
    return total_drift


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Normalizes a dictionary of weights so that their sum equals 1.0.
    
    Args:
        weights: Dictionary mapping assets to their raw weights.
        
    Returns:
        Dictionary mapping assets to normalized weights.
    """
    total = sum(weights.values())
    if total == 0.0:
        return weights
    return {ticker: weight / total for ticker, weight in weights.items()}

