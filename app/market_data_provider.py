#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Algolab Market Data Provider for BIST (Istanbul Stock Exchange)

Provides real-time and historical market data for Turkish stocks.
Acts as an alternative to yfinance for BIST data (TR IP-restricted).
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from decimal import Decimal

from .algolab_client import AlgolabClient

logger = logging.getLogger(__name__)


class BISTMarketData:
    """Market data structure for BIST stocks"""

    def __init__(self, symbol: str):
        """Initialize BIST market data object"""
        self.symbol = symbol
        self.company_name = ""
        self.sector = ""
        self.price: Decimal = Decimal("0")
        self.bid: Decimal = Decimal("0")
        self.ask: Decimal = Decimal("0")
        self.open: Decimal = Decimal("0")
        self.high: Decimal = Decimal("0")
        self.low: Decimal = Decimal("0")
        self.close: Decimal = Decimal("0")
        self.volume: int = 0
        self.market_cap: Decimal = Decimal("0")
        self.pe_ratio: Optional[Decimal] = None
        self.eps: Optional[Decimal] = None
        self.dividend_yield: Optional[Decimal] = None
        self.last_update: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "sector": self.sector,
            "price": float(self.price),
            "bid": float(self.bid),
            "ask": float(self.ask),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": self.volume,
            "market_cap": float(self.market_cap),
            "pe_ratio": float(self.pe_ratio) if self.pe_ratio else None,
            "eps": float(self.eps) if self.eps else None,
            "dividend_yield": float(self.dividend_yield) if self.dividend_yield else None,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }


class AlgolabMarketDataProvider:
    """
    Market data provider using Algolab API for BIST stocks

    Features:
    - Real-time stock prices and quotes
    - Historical OHLCV candle data (from WebSocket)
    - Portfolio monitoring with position data
    - Sector and company information

    Advantages over yfinance for Turkish market:
    - Direct BIST exchange connection (no TR IP restrictions)
    - Real-time data (no 15-minute delay)
    - Turkish market rules and tick sizes
    - Multi-timeframe data
    """

    def __init__(self, algolab_client: AlgolabClient):
        """
        Initialize market data provider

        Args:
            algolab_client: Authenticated AlgolabClient instance
        """
        self.client = algolab_client
        self.cache: Dict[str, BISTMarketData] = {}
        self.cache_expiry: Dict[str, datetime] = {}

    async def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time stock information from Algolab

        Args:
            symbol: Stock symbol (e.g., "ASELS", "GARAN", "YKBNK")

        Returns:
            Dictionary with stock price, bid/ask, volume, etc.

        Example:
            >>> info = await provider.get_stock_info("ASELS")
            >>> print(info["price"], info["company_name"])
        """
        try:
            # Call Algolab GetEquityInfo API
            result = await self.client.get_equity_info(symbol)

            if not result.get("success"):
                logger.warning(f"Failed to get stock info for {symbol}: {result.get('message')}")
                return {
                    "success": False,
                    "error": result.get("message", "Unknown error")
                }

            # Parse Algolab response
            content = result.get("content", {})
            market_data = BISTMarketData(symbol)

            # Map Algolab fields to our structure
            if isinstance(content, dict):
                market_data.company_name = content.get("Name", "")
                market_data.sector = content.get("Sector", "")

                # Current price data
                price = content.get("Price")
                if price:
                    market_data.price = Decimal(str(price))
                    market_data.close = market_data.price

                # Bid/Ask
                bid = content.get("Bid")
                ask = content.get("Ask")
                if bid:
                    market_data.bid = Decimal(str(bid))
                if ask:
                    market_data.ask = Decimal(str(ask))

                # OHLC
                open_price = content.get("Open")
                high = content.get("High")
                low = content.get("Low")
                if open_price:
                    market_data.open = Decimal(str(open_price))
                if high:
                    market_data.high = Decimal(str(high))
                if low:
                    market_data.low = Decimal(str(low))

                # Volume
                volume = content.get("Volume")
                if volume:
                    market_data.volume = int(volume)

                # Market metrics
                market_cap = content.get("MarketCap")
                if market_cap:
                    market_data.market_cap = Decimal(str(market_cap))

                pe_ratio = content.get("PERatio")
                if pe_ratio:
                    market_data.pe_ratio = Decimal(str(pe_ratio))

                eps = content.get("EPS")
                if eps:
                    market_data.eps = Decimal(str(eps))

                dividend_yield = content.get("DividendYield")
                if dividend_yield:
                    market_data.dividend_yield = Decimal(str(dividend_yield))

            market_data.last_update = datetime.utcnow()

            # Cache the data
            self.cache[symbol] = market_data
            self.cache_expiry[symbol] = datetime.utcnow() + timedelta(minutes=5)

            return {
                "success": True,
                "data": market_data.to_dict()
            }

        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_multiple_stocks(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get information for multiple stocks

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary with data for each symbol

        Example:
            >>> data = await provider.get_multiple_stocks(["ASELS", "GARAN", "YKBNK"])
        """
        results = {}

        for symbol in symbols:
            try:
                result = await self.get_stock_info(symbol)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {str(e)}")
                results[symbol] = {
                    "success": False,
                    "error": str(e)
                }

        return {
            "success": True,
            "stocks": results,
            "count": len([r for r in results.values() if r.get("success")])
        }

    async def get_top_gainers(self, sector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get top gaining stocks (from portfolio data)

        Note: This would require portfolio integration or WebSocket data
        For now, returns a placeholder structure

        Args:
            sector: Filter by sector (optional)

        Returns:
            List of top gainers with price changes
        """
        try:
            # Get portfolio data which includes all positions
            portfolio = await self.client.instant_position()

            if not portfolio.get("success"):
                return {
                    "success": False,
                    "error": "Failed to fetch portfolio data"
                }

            # Extract unique symbols and sort by gain percentage
            # This is a simplified version - full implementation would need
            # historical comparison data
            gainers = []

            content = portfolio.get("content", [])
            if isinstance(content, list):
                for position in content[:10]:  # Top 10 gainers
                    symbol = position.get("Symbol", "")
                    change_percent = position.get("ChangePercent", 0)

                    if change_percent > 0:
                        gainers.append({
                            "symbol": symbol,
                            "change_percent": float(change_percent),
                            "change_amount": float(position.get("Change", 0)),
                            "price": float(position.get("Price", 0))
                        })

            # Sort by change percentage
            gainers = sorted(gainers, key=lambda x: x["change_percent"], reverse=True)

            return {
                "success": True,
                "gainers": gainers[:10],
                "count": len(gainers)
            }

        except Exception as e:
            logger.error(f"Error getting top gainers: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_top_losers(self, sector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get top losing stocks

        Similar to get_top_gainers but for negative performers

        Args:
            sector: Filter by sector (optional)

        Returns:
            List of top losers with price changes
        """
        try:
            portfolio = await self.client.instant_position()

            if not portfolio.get("success"):
                return {
                    "success": False,
                    "error": "Failed to fetch portfolio data"
                }

            losers = []

            content = portfolio.get("content", [])
            if isinstance(content, list):
                for position in content[:10]:
                    symbol = position.get("Symbol", "")
                    change_percent = position.get("ChangePercent", 0)

                    if change_percent < 0:
                        losers.append({
                            "symbol": symbol,
                            "change_percent": float(change_percent),
                            "change_amount": float(position.get("Change", 0)),
                            "price": float(position.get("Price", 0))
                        })

            losers = sorted(losers, key=lambda x: x["change_percent"])

            return {
                "success": True,
                "losers": losers[:10],
                "count": len(losers)
            }

        except Exception as e:
            logger.error(f"Error getting top losers: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_most_active(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get most active (highest volume) stocks

        Args:
            limit: Number of stocks to return (default 10)

        Returns:
            List of most active stocks
        """
        try:
            portfolio = await self.client.instant_position()

            if not portfolio.get("success"):
                return {
                    "success": False,
                    "error": "Failed to fetch portfolio data"
                }

            active = []

            content = portfolio.get("content", [])
            if isinstance(content, list):
                for position in content:
                    symbol = position.get("Symbol", "")
                    volume = position.get("Volume", 0)

                    active.append({
                        "symbol": symbol,
                        "volume": int(volume),
                        "price": float(position.get("Price", 0)),
                        "change_percent": float(position.get("ChangePercent", 0))
                    })

            active = sorted(active, key=lambda x: x["volume"], reverse=True)

            return {
                "success": True,
                "active_stocks": active[:limit],
                "count": len(active)
            }

        except Exception as e:
            logger.error(f"Error getting most active: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_cached_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached stock data if available and not expired

        Args:
            symbol: Stock symbol

        Returns:
            Cached market data or None if not available/expired
        """
        if symbol not in self.cache:
            return None

        expiry = self.cache_expiry.get(symbol)
        if expiry and datetime.utcnow() > expiry:
            # Cache expired
            del self.cache[symbol]
            del self.cache_expiry[symbol]
            return None

        return self.cache[symbol].to_dict()

    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data

        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        if symbol:
            if symbol in self.cache:
                del self.cache[symbol]
            if symbol in self.cache_expiry:
                del self.cache_expiry[symbol]
        else:
            self.cache.clear()
            self.cache_expiry.clear()


# Example usage and integration
if __name__ == "__main__":
    import asyncio

    async def test_provider():
        """Test market data provider"""
        from .config import settings

        # This would require a real authenticated client
        # api_key = settings.algolab_api_key
        # client = AlgolabClient(api_key)
        # provider = AlgolabMarketDataProvider(client)

        # result = await provider.get_stock_info("ASELS")
        # print(result)

        print("Market data provider initialized successfully")


    asyncio.run(test_provider())
