"""
Central Symbol Mapping Module for Fyers API v3.

Maps UI display names to exact Fyers tickers.
All symbol conversions go through this module.
"""

from typing import Dict

# Central mapping: UI display name -> Fyers ticker
SYMBOL_TO_FYERS: Dict[str, str] = {
    # Indices
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "NIFTY BANK": "NSE:NIFTYBANK-INDEX",
    "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "BANKEX": "BSE:BANKEX-INDEX",
    "INDIA VIX": "NSE:INDIAVIX-INDEX",
    "VIX": "NSE:INDIAVIX-INDEX",
    
    # Equities (common aliases)
    "RELIANCE IND.": "NSE:RELIANCE-EQ",
    "RELIANCE INDUSTRIES": "NSE:RELIANCE-EQ",
    "RELIANCE": "NSE:RELIANCE-EQ",
    "HDFC BANK": "NSE:HDFCBANK-EQ",
    "HDFCBANK": "NSE:HDFCBANK-EQ",
    "TCS": "NSE:TCS-EQ",
    "TATA CONSULTANCY": "NSE:TCS-EQ",
    "INFOSYS": "NSE:INFY-EQ",
    "INFY": "NSE:INFY-EQ",
    "ICICI BANK": "NSE:ICICIBANK-EQ",
    "ICICIBANK": "NSE:ICICIBANK-EQ",
    "SBI": "NSE:SBIN-EQ",
    "SBIN": "NSE:SBIN-EQ",
    "HDFC": "NSE:HDFC-EQ",
    "KOTAK BANK": "NSE:KOTAKBANK-EQ",
    "KOTAKBANK": "NSE:KOTAKBANK-EQ",
    "AXIS BANK": "NSE:AXISBANK-EQ",
    "AXISBANK": "NSE:AXISBANK-EQ",
    "LT": "NSE:LT-EQ",
    "LARSEN": "NSE:LT-EQ",
    "BAJFINANCE": "NSE:BAJFINANCE-EQ",
    "BAJAJ FINANCE": "NSE:BAJFINANCE-EQ",
    "BAJFINSERV": "NSE:BAJAJFINSV-EQ",
    "BAJAJ FINSERV": "NSE:BAJAJFINSV-EQ",
    "MARUTI": "NSE:MARUTI-EQ",
    "MARUTI SUZUKI": "NSE:MARUTI-EQ",
    "ASIAN PAINTS": "NSE:ASIANPAINT-EQ",
    "ASIANPAINT": "NSE:ASIANPAINT-EQ",
    "HINDUNILVR": "NSE:HINDUNILVR-EQ",
    "HUL": "NSE:HINDUNILVR-EQ",
    "ITC": "NSE:ITC-EQ",
    "SUN PHARMA": "NSE:SUNPHARMA-EQ",
    "SUNPHARMA": "NSE:SUNPHARMA-EQ",
    "TITAN": "NSE:TITAN-EQ",
    "WIPRO": "NSE:WIPRO-EQ",
    "ONGC": "NSE:ONGC-EQ",
    "NTPC": "NSE:NTPC-EQ",
    "POWERGRID": "NSE:POWERGRID-EQ",
    "POWER GRID": "NSE:POWERGRID-EQ",
    "COAL INDIA": "NSE:COALINDIA-EQ",
    "COALINDIA": "NSE:COALINDIA-EQ",
    "BPCL": "NSE:BPCL-EQ",
    "IOC": "NSE:IOC-EQ",
    "HINDALCO": "NSE:HINDALCO-EQ",
    "TATA STEEL": "NSE:TATASTEEL-EQ",
    "TATASTEEL": "NSE:TATASTEEL-EQ",
    "JSW STEEL": "NSE:JSWSTEEL-EQ",
    "JSWSTEEL": "NSE:JSWSTEEL-EQ",
    "ADANI PORTS": "NSE:ADANIPORTS-EQ",
    "ADANIPORTS": "NSE:ADANIPORTS-EQ",
    "ADANI ENTERPRISES": "NSE:ADANIENT-EQ",
    "ADANIENT": "NSE:ADANIENT-EQ",
    "BAJAJ AUTO": "NSE:BAJAJ-AUTO-EQ",
    "BAJAJAUTO": "NSE:BAJAJ-AUTO-EQ",
    "HERO MOTOCORP": "NSE:HEROMOTOCO-EQ",
    "HEROMOTOCO": "NSE:HEROMOTOCO-EQ",
    "EICHER MOTORS": "NSE:EICHERMOT-EQ",
    "EICHERMOT": "NSE:EICHERMOT-EQ",
    "TECH MAHINDRA": "NSE:TECHM-EQ",
    "TECHM": "NSE:TECHM-EQ",
    "HCL TECH": "NSE:HCLTECH-EQ",
    "HCLTECH": "NSE:HCLTECH-EQ",
    "CIPLA": "NSE:CIPLA-EQ",
    "DR REDDY": "NSE:DRREDDY-EQ",
    "DRREDDY": "NSE:DRREDDY-EQ",
    "APOLLO HOSPITALS": "NSE:APOLLOHOSP-EQ",
    "APOLLOHOSP": "NSE:APOLLOHOSP-EQ",
    "DIVIS LAB": "NSE:DIVISLAB-EQ",
    "DIVISLAB": "NSE:DIVISLAB-EQ",
    "BRITANNIA": "NSE:BRITANNIA-EQ",
    "NESTLE": "NSE:NESTLEIND-EQ",
    "NESTLE INDIA": "NSE:NESTLEIND-EQ",
    "TATA CONSUMER": "NSE:TATACONSUM-EQ",
    "TATACONSUM": "NSE:TATACONSUM-EQ",
    "GRASIM": "NSE:GRASIM-EQ",
    "ULTRATECH": "NSE:ULTRACEMCO-EQ",
    "ULTRATECH CEMENT": "NSE:ULTRACEMCO-EQ",
    "SHREE CEMENT": "NSE:SHREECEM-EQ",
    "SHREECEM": "NSE:SHREECEM-EQ",
    "AMBUJA CEMENTS": "NSE:AMBUJACEM-EQ",
    "AMBUJACEM": "NSE:AMBUJACEM-EQ",
    "ACC": "NSE:ACC-EQ",
    "INDUSIND BANK": "NSE:INDUSINDBK-EQ",
    "INDUSINDBK": "NSE:INDUSINDBK-EQ",
    "YES BANK": "NSE:YESBANK-EQ",
    "YESBANK": "NSE:YESBANK-EQ",
    "FEDERAL BANK": "NSE:FEDERALBNK-EQ",
    "FEDERALBNK": "NSE:FEDERALBNK-EQ",
    "IDFC FIRST": "NSE:IDFCFIRSTB-EQ",
    "IDFCFIRSTB": "NSE:IDFCFIRSTB-EQ",
    "BANK OF BARODA": "NSE:BANKBARODA-EQ",
    "BANKBARODA": "NSE:BANKBARODA-EQ",
    "PNB": "NSE:PNB-EQ",
    "PUNJAB NATIONAL": "NSE:PNB-EQ",
    "CANBK": "NSE:CANBK-EQ",
    "CANARA BANK": "NSE:CANBK-EQ",
    "UNION BANK": "NSE:UNIONBANK-EQ",
    "UNIONBANK": "NSE:UNIONBANK-EQ",
    "INDIAN BANK": "NSE:INDIANB-EQ",
    "INDIANB": "NSE:INDIANB-EQ",
}

# Reverse mapping for display: Fyers ticker -> UI display name
FYERS_TO_SYMBOL: Dict[str, str] = {v: k for k, v in SYMBOL_TO_FYERS.items()}


def to_fyers(symbol: str) -> str:
    """
    Convert a UI display symbol to a Fyers ticker.
    
    Rules:
    - If input already contains a colon (e.g., "NSE:NIFTY50-INDEX"), return as-is
    - Look up in SYMBOL_TO_FYERS map (case-insensitive, whitespace-normalized)
    - If not found and looks like an equity, return NSE:<SYMBOL>-EQ
    - If not found, return original
    """
    if not symbol:
        return symbol
    
    s = symbol.strip()
    
    # Already a Fyers ticker (contains colon)
    if ":" in s:
        return s
    
    # Normalize: uppercase, collapse whitespace
    key = " ".join(s.upper().split())
    
    # Direct lookup
    if key in SYMBOL_TO_FYERS:
        return SYMBOL_TO_FYERS[key]
    
    # Unknown bare name: assume NSE equity
    # Remove any -EQ suffix if present and re-add
    clean = key.replace("-EQ", "").replace("-INDEX", "")
    return f"NSE:{clean}-EQ"


def to_ui(symbol: str) -> str:
    """
    Convert a Fyers ticker to a UI display name.
    
    If not in reverse map, return the symbol as-is.
    """
    if not symbol:
        return symbol
    
    return FYERS_TO_SYMBOL.get(symbol, symbol)


def is_fyers_ticker(symbol: str) -> bool:
    """Check if symbol is already in Fyers ticker format (contains colon)."""
    return ":" in symbol if symbol else False


def get_all_mappings() -> Dict[str, str]:
    """Return all UI -> Fyers mappings."""
    return SYMBOL_TO_FYERS.copy()