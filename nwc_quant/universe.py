"""
A liquid, sector-diversified universe (~75 large caps across all 11 GICS
sectors). This is the ranked cross-section — breadth is where the edge lives.

Edit freely: add S&P 500 names, swap sectors, extend to a few hundred. The only
rule that matters is DIVERSITY — the engine sector-neutralizes, so you want real
coverage across sectors, not 40 tech names.
"""

UNIVERSE = {
    # Information Technology
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AVGO": "Tech",
    "ORCL": "Tech", "CRM": "Tech", "ADBE": "Tech", "AMD": "Tech",
    "CSCO": "Tech", "ACN": "Tech", "QCOM": "Tech", "TXN": "Tech",
    "IBM": "Tech", "NOW": "Tech", "INTC": "Tech",
    # Communication Services
    "GOOGL": "Communication", "META": "Communication", "NFLX": "Communication",
    "DIS": "Communication", "VZ": "Communication", "TMUS": "Communication",
    "CMCSA": "Communication", "T": "Communication",
    # Consumer Discretionary
    "AMZN": "Discretionary", "TSLA": "Discretionary", "HD": "Discretionary",
    "MCD": "Discretionary", "NKE": "Discretionary", "LOW": "Discretionary",
    "SBUX": "Discretionary", "BKNG": "Discretionary", "TJX": "Discretionary",
    # Consumer Staples
    "COST": "Staples", "WMT": "Staples", "PG": "Staples", "KO": "Staples",
    "PEP": "Staples", "PM": "Staples", "MDLZ": "Staples",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials",
    "V": "Financials", "MA": "Financials", "GS": "Financials",
    "MS": "Financials", "AXP": "Financials", "BLK": "Financials",
    "SCHW": "Financials",
    # Health Care
    "JNJ": "Health", "UNH": "Health", "LLY": "Health", "ABBV": "Health",
    "MRK": "Health", "PFE": "Health", "TMO": "Health", "ABT": "Health",
    "DHR": "Health", "AMGN": "Health",
    # Industrials
    "CAT": "Industrials", "BA": "Industrials", "HON": "Industrials",
    "UPS": "Industrials", "GE": "Industrials", "RTX": "Industrials",
    "DE": "Industrials", "LMT": "Industrials",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities",
    # Materials
    "LIN": "Materials", "SHW": "Materials", "FCX": "Materials",
    # Real Estate
    "PLD": "RealEstate", "AMT": "RealEstate", "EQIX": "RealEstate",
}
