"""
Mock data for Algolab Bridge Server
Used when ALGOLAB_USE_MOCK is True
"""

from datetime import datetime, timedelta

# Mock Stock Data
MOCK_STOCK_DATA = {
    "ASELS": {
        "symbol": "ASELS",
        "desc": "ASELSAN ELEKTRONIK SANAYI",
        "price": 45.50,
        "bid": 45.45,
        "ask": 45.55,
        "open": 44.80,
        "high": 46.20,
        "low": 44.50,
        "close": 45.50,
        "volume": 1250000,
        "change": 1.56,
        "change_rate": 3.55,
        "market_cap": 10200000000,
        "pe_ratio": 12.5,
    },
    "THYAO": {
        "symbol": "THYAO",
        "desc": "TURK HAVA YOLLARI",
        "price": 245.50,
        "bid": 245.40,
        "ask": 245.60,
        "open": 240.00,
        "high": 248.00,
        "low": 239.50,
        "close": 245.50,
        "volume": 5500000,
        "change": 5.50,
        "change_rate": 2.29,
        "market_cap": 340000000000,
        "pe_ratio": 4.5,
    },
    "GARAN": {
        "symbol": "GARAN",
        "desc": "TURKIYE GARANTI BANKASI",
        "price": 65.25,
        "bid": 65.20,
        "ask": 65.30,
        "open": 64.00,
        "high": 66.00,
        "low": 63.80,
        "close": 65.25,
        "volume": 8500000,
        "change": 1.25,
        "change_rate": 1.95,
        "market_cap": 275000000000,
        "pe_ratio": 3.8,
    }
}

# Mock Portfolio Positions
MOCK_POSITIONS = [
    {
        "symbol": "ASELS",
        "cost": 42.50,
        "amount": 1000,
        "price": 45.50,
        "total": 45500.00,
        "profit": 3000.00,
        "profit_rate": 7.05,
        "available": 1000
    },
    {
        "symbol": "THYAO",
        "cost": 230.00,
        "amount": 500,
        "price": 245.50,
        "total": 122750.00,
        "profit": 7750.00,
        "profit_rate": 6.74,
        "available": 500
    }
]

# Mock Cash Flow
MOCK_CASH_FLOW = {
    "t0": 15000.00,
    "t1": 25000.00,
    "t2": 50000.00,
    "blocked": 5000.00,
    "total": 95000.00,
    "limit": 100000.00
}

# Mock Subaccounts
MOCK_SUBACCOUNTS = [
    {
        "number": "100",
        "name": "MAIN ACCOUNT",
        "tradeLimit": "100000.00",
        "creditLimit": "50000.00"
    },
    {
        "number": "101",
        "name": "SAVINGS",
        "tradeLimit": "0.00",
        "creditLimit": "0.00"
    }
]

def get_mock_stock_detail(symbol: str):
    """Get detailed mock data for a stock"""
    data = MOCK_STOCK_DATA.get(symbol, MOCK_STOCK_DATA["ASELS"]).copy()
    data["symbol"] = symbol
    return data
