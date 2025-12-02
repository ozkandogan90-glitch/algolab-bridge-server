# Algolab Market Data Provider - BIST Data Integration

## Overview

The Algolab Market Data Provider enables real-time and historical market data access for BIST (Istanbul Stock Exchange) stocks directly through Algolab API. It acts as a **yfinance alternative** for Turkish market data without IP restrictions.

## Key Features

✅ **Real-Time Data Access**
- Current stock prices, bid/ask spreads
- Intraday OHLC (Open, High, Low, Close)
- Trade volume and market metrics
- PE ratio, EPS, dividend yield

✅ **Data Caching**
- 5-minute cache to minimize API calls
- Cache expiry management
- Reduce API rate limiting issues

✅ **Multi-Stock Support**
- Fetch single stock info
- Batch multiple stocks (up to 10 at once)
- Top gainers/losers/most active

✅ **No IP Restrictions**
- Works from any location (BIST'e TR IP başlangıcından muaf)
- Direct integration with Algolab platform
- Real-time data without 15-minute delay

## Architecture

```
┌─────────────────┐
│  Frontend/API   │
└────────┬────────┘
         │ HTTP Request
         │ (JWT Authenticated)
         ▼
┌─────────────────────────────────┐
│    Bridge Server Main.py         │
│    ├─ auth_router               │
│    ├─ trading_router            │
│    ├─ portfolio_router          │
│    └─ market_router ◄──── NEW   │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Market Data Provider             │
│ (market_data_provider.py)        │
│                                  │
│ AlgolabMarketDataProvider        │
│ ├─ get_stock_info()             │
│ ├─ get_multiple_stocks()        │
│ ├─ get_top_gainers()            │
│ ├─ get_top_losers()             │
│ ├─ get_most_active()            │
│ └─ Cache Management             │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│    Algolab API Client            │
│    (algolab_client.py)           │
│                                  │
│ AlgolabClient                    │
│ ├─ get_equity_info()            │
│ ├─ instant_position()           │
│ ├─ Encryption (AES)             │
│ ├─ Rate Limiting (5s min)       │
│ └─ Request Signing (Checker)    │
└────────┬─────────────────────────┘
         │ HTTPS + AES Encryption
         ▼
┌──────────────────────────────────┐
│   Algolab API (BIST Server)      │
│   https://www.algolab.com.tr/api │
└──────────────────────────────────┘
```

## API Endpoints

### 1. Get Single Stock Info
```http
POST /bridge/stock-info
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
    "session_id": "xyz123",
    "symbol": "ASELS"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "symbol": "ASELS",
        "company_name": "Aselsan Elektronik Sanayi ve Ticaret A.Ş.",
        "sector": "Technology",
        "price": 45.50,
        "bid": 45.45,
        "ask": 45.55,
        "open": 44.80,
        "high": 46.20,
        "low": 44.50,
        "close": 45.50,
        "volume": 1500000,
        "market_cap": 54000000000,
        "pe_ratio": 18.5,
        "eps": 2.46,
        "dividend_yield": 1.2,
        "last_update": "2025-12-01T14:30:00Z"
    },
    "source": "live" | "cache"
}
```

### 2. Get Multiple Stocks
```http
POST /bridge/multiple-stocks
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
    "session_id": "xyz123",
    "symbols": ["ASELS", "GARAN", "YKBNK", "SASA"]
}
```

**Response:**
```json
{
    "success": true,
    "stocks": {
        "ASELS": {...},
        "GARAN": {...},
        "YKBNK": {...},
        "SASA": {...}
    },
    "count": 4
}
```

### 3. Top Gainers
```http
POST /bridge/top-gainers
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
    "session_id": "xyz123"
}
```

**Response:**
```json
{
    "success": true,
    "gainers": [
        {
            "symbol": "ASELS",
            "change_percent": 3.5,
            "change_amount": 1.50,
            "price": 45.50
        },
        {
            "symbol": "GARAN",
            "change_percent": 2.8,
            "change_amount": 0.75,
            "price": 27.50
        }
    ],
    "count": 2
}
```

### 4. Top Losers
```http
POST /bridge/top-losers
Authorization: Bearer <JWT_TOKEN>

{
    "session_id": "xyz123"
}
```

Returns bottom 10 stocks by negative percentage change.

### 5. Most Active (Highest Volume)
```http
POST /bridge/most-active?limit=10
Authorization: Bearer <JWT_TOKEN>

{
    "session_id": "xyz123"
}
```

**Response:**
```json
{
    "success": true,
    "active_stocks": [
        {
            "symbol": "YKBNK",
            "volume": 50000000,
            "price": 9.85,
            "change_percent": 1.2
        },
        {
            "symbol": "SASA",
            "volume": 35000000,
            "price": 15.45,
            "change_percent": -0.5
        }
    ],
    "count": 10
}
```

## Implementation Details

### 1. BISTMarketData Class
Represents a single stock's market data:
```python
market_data = BISTMarketData("ASELS")
market_data.price = Decimal("45.50")
market_data.bid = Decimal("45.45")
market_data.ask = Decimal("45.55")
market_data.volume = 1500000
market_data.to_dict()  # Convert to JSON-serializable dict
```

### 2. AlgolabMarketDataProvider Class
Main provider class with methods:

**get_stock_info(symbol)**
- Fetches real-time data from Algolab GetEquityInfo API
- Maps Algolab response fields to our structure
- Caches result for 5 minutes
- Returns parsed market data

**get_multiple_stocks(symbols)**
- Batch fetch multiple stocks
- Returns combined results
- Parallel fetching where possible

**get_top_gainers()/get_top_losers()**
- Uses portfolio data to calculate changes
- Sorts by percentage change
- Returns top 10

**get_most_active(limit)**
- Ranks by trading volume
- Returns most traded stocks
- Configurable limit (1-50)

### 3. Caching Strategy

**Why Caching?**
- Algolab has 5-second minimum request interval
- Reduces redundant API calls
- Improves response times
- Stays compliant with rate limits

**Cache Structure:**
```python
self.cache: Dict[str, BISTMarketData]        # Symbol → Data
self.cache_expiry: Dict[str, datetime]       # Symbol → Expiry time
```

**Expiry Policy:**
- Default: 5 minutes
- Configurable per market type
- Automatic cleanup on expiry

## Integration with Backend API

The Bridge Server's market data endpoints should be integrated into the main Backend API:

```python
# backend/api/routers/market_data/algolab_market_data.py

@router.get("/api/stocks/{symbol}")
async def get_stock_info(
    symbol: str,
    session_id: str = Query(..., description="Algolab session")
):
    """
    Get BIST stock information via Algolab

    Alternative to yfinance for Turkish stocks
    """
    # Call Bridge Server: POST /bridge/stock-info
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.ALGOLAB_BRIDGE_URL}/bridge/stock-info",
            json={"session_id": session_id, "symbol": symbol},
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        return response.json()


@router.get("/api/market-screener/gainers")
async def get_top_gainers(
    session_id: str = Query(...)
):
    """Get top gaining stocks from BIST"""
    # Call Bridge Server: POST /bridge/top-gainers
    ...


@router.get("/api/market-screener/losers")
async def get_top_losers(session_id: str = Query(...)):
    """Get top losing stocks from BIST"""
    ...


@router.get("/api/market-screener/active")
async def get_most_active(
    limit: int = Query(10, ge=1, le=50),
    session_id: str = Query(...)
):
    """Get most active stocks by volume"""
    ...
```

## BIST Stock List

Common Turkish stocks available through Algolab:

| Symbol | Company | Sector |
|--------|---------|--------|
| ASELS | Aselsan | Technology |
| GARAN | Garanti BBVA | Banking |
| YKBNK | Yapı Kredi Bank | Banking |
| SASA | Sabancı Holding | Holding |
| AKBNK | Akbank | Banking |
| AKKO | Akkaya Orman | Manufacturing |
| BIMAS | BİM Stores | Retail |
| GOLTS | GoBank/Trendyol | E-Commerce |
| IBANK | İşbank | Banking |
| KCHOL | Koç Holding | Holding |
| TURSG | Turkish Airlines | Transportation |
| UPVCU | United Ventures | Venture |

## Comparison: Algolab vs yfinance

| Feature | Algolab | yfinance |
|---------|---------|----------|
| Real-time BIST Data | ✅ Yes | ⚠️ 15-min delayed |
| IP Restrictions | ❌ None | ✅ None |
| Authentication | ✅ Required | ❌ None |
| Historical Data | ✅ Via WebSocket | ✅ Yes |
| Multi-Timeframe | ✅ 1m-1d | ✅ 1m-1y |
| Bid/Ask Data | ✅ Yes | ❌ No |
| Volume Data | ✅ Detailed | ✅ Yes |
| Financial Metrics | ✅ PE, EPS, Div | ✅ Limited |
| Rate Limit | 5 sec/request | Unlimited |
| Cost | ✅ Included | ❌ Free (unreliable) |

## Performance Considerations

**Rate Limiting**
- Algolab enforces 5-second minimum between requests
- Built into AlgolabClient via RateLimiter
- Batch requests to minimize calls

**Caching Strategy**
- 5-minute cache for single stocks
- Reduces redundant API calls
- `cache_expiry` tracks expiration

**Parallelization**
- `get_multiple_stocks()` fetches sequentially (respects 5-sec limit)
- Could be improved with request queuing

**Network Optimization**
- HTTPS only (Algolab requirement)
- AES-256 encryption built-in
- HTTP Keep-Alive via AsyncClient

## Error Handling

All endpoints return structured error responses:

```json
{
    "success": false,
    "error": "Session invalid or expired"
}
```

Common errors:
- Invalid session_id → 401 Unauthorized
- Algolab API error → 500 Internal Server Error
- Rate limit exceeded → 429 Too Many Requests
- Network timeout → 504 Bad Gateway

## Future Enhancements

🔄 **Planned Improvements:**
1. Historical OHLCV data via WebSocket
2. Sector-based filtering
3. Watchlist management
4. Price alerts/notifications
5. Technical indicator pre-calculation
6. Candlestick pattern recognition
7. Volume profile analysis
8. Market breadth indicators (gainers/losers/flat ratio)

## Usage Example

```python
# Initialize authenticated client
api_key = "APIKEY-xxx=="
client = AlgolabClient(api_key)
await client.login_user(username, password)  # SMS verification
await client.login_user_control(token, sms_code)

# Create market data provider
provider = AlgolabMarketDataProvider(client)

# Get single stock
info = await provider.get_stock_info("ASELS")
print(f"ASELS Price: {info['data']['price']}")

# Get multiple stocks
data = await provider.get_multiple_stocks(["GARAN", "YKBNK"])
for symbol, info in data['stocks'].items():
    print(f"{symbol}: {info['data']['price']}")

# Get market leaders
gainers = await provider.get_top_gainers()
for gainer in gainers['gainers']:
    print(f"{gainer['symbol']}: +{gainer['change_percent']}%")

await client.close()
```

## Environment Variables

Required in `bridge_server/.env`:
```
ALGOLAB_API_URL=https://www.algolab.com.tr/api
ALGOLAB_HOSTNAME=www.algolab.com.tr
BRIDGE_JWT_SECRET=<shared-secret>
MIN_REQUEST_INTERVAL_SECONDS=5.0
```

## Testing

Run tests:
```bash
cd bridge_server
python -m pytest tests/test_market_data_provider.py -v
```

Test coverage:
- Single stock info retrieval
- Multiple stocks batch fetch
- Top gainers/losers calculation
- Cache hit/miss scenarios
- Rate limit compliance
- Error handling

---

**Last Updated:** December 1, 2025
**Version:** 1.0 - BIST Market Data Provider
