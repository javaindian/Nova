import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

class YFinanceFetcher:
    def __init__(self):
        """
        Initializes the yfinance fetcher.
        """
        print("YFinanceFetcher initialized.")

    def _map_timeframe(self, timeframe_str):
        """
        Maps a common timeframe string (e.g., '15m', '1h', '1d') to yfinance interval.
        yfinance intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        """
        mapping = {
            '1m': '1m', '3m': '2m', # yf doesn't have 3m, using 2m as closest. Or could aggregate 1m.
            '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '60m': '60m', # '1h' and '60m' are equivalent for yf for recent data
            '2h': '2h', # yfinance might not directly support 2h. May need to aggregate 1h.
            '4h': '4h', # yfinance might not directly support 4h. May need to aggregate 1h.
            '1d': '1d', '1w': '1wk', '1M': '1mo'
        }
        # For intervals like 2h, 4h, yfinance might not support them directly for all periods.
        # It's often better to fetch a smaller granularity (e.g., 1h) and resample.
        # However, yfinance has added more interval supports over time.
        # Let's try direct mapping and handle potential errors or resampling later if needed.

        # A common issue: for intraday data (e.g. '1m', '15m'), yfinance has limitations on date range
        # e.g., '1m' is usually limited to the last 7 days. '15m' up to 60 days.

        return mapping.get(timeframe_str.lower(), timeframe_str) # Default to original if not in map

    def get_historical_data(self, symbol, timeframe, start_date, end_date=None, proxy=None):
        """
        Fetches historical OHLCV data for a given symbol and timeframe.

        Args:
            symbol (str): The stock symbol (e.g., "MSFT", "RELIANCE.NS").
            timeframe (str): The timeframe string (e.g., "15m", "1h", "1d").
            start_date (str or datetime): The start date for the data.
            end_date (str or datetime, optional): The end date for the data. Defaults to today.
            proxy (str, optional): Proxy server URL if needed.

        Returns:
            pandas.DataFrame: A DataFrame with OHLCV data, indexed by Datetime.
                              Returns None if an error occurs.
        """
        yf_interval = self._map_timeframe(timeframe)

        if isinstance(start_date, datetime):
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = start_date

        if end_date:
            if isinstance(end_date, datetime):
                # yfinance end_date is exclusive for daily and above, inclusive for intraday.
                # To be safe and ensure we get data for the end_date if it's intraday,
                # or up to the end_date for daily, we can add a day if it's just a date.
                if end_date.time() == datetime.min.time(): # If it's just a date (no time part)
                     end_date_dt = end_date + timedelta(days=1)
                else:
                    end_date_dt = end_date
                end_date_str = end_date_dt.strftime('%Y-%m-%d')
            else: # If end_date is already a string
                try:
                    # Attempt to parse to ensure it's a valid date string, then add a day
                    end_date_dt_parsed = pd.to_datetime(end_date)
                    if end_date_dt_parsed.time() == datetime.min.time():
                        end_date_dt_parsed += timedelta(days=1)
                    end_date_str = end_date_dt_parsed.strftime('%Y-%m-%d')
                except ValueError:
                    print(f"Error: Invalid end_date string format: {end_date}")
                    return None
        else:
            end_date_str = None # yfinance will fetch up to the most recent data

        print(f"YFinanceFetcher: Fetching {symbol} for interval {yf_interval} from {start_date_str} to {end_date_str}")

        try:
            ticker = yf.Ticker(symbol)
            # Note on yfinance period vs start/end:
            # For intraday data, 'period' is often more reliable or required.
            # Max period for 1m is 7d. Max for <1h intervals is 60d, unless using `period`.
            # If start_date and end_date span too long for the interval, yfinance might return daily data or error.

            # Logic to handle yfinance period limitations for intraday data:
            is_intraday = yf_interval not in ['1d', '5d', '1wk', '1mo', '3mo']
            if is_intraday:
                s_date = pd.to_datetime(start_date_str)
                e_date = pd.to_datetime(end_date_str) if end_date_str else pd.to_datetime(datetime.now().date() + timedelta(days=1))
                delta_days = (e_date - s_date).days

                if yf_interval in ['1m'] and delta_days > 7:
                    print(f"Warning: yfinance '1m' data is limited to 7 days. Requested: {delta_days} days. Adjusting start_date or this may fail/return limited data.")
                    # Consider fetching in chunks or adjusting start_date if strict adherence is needed.
                    # For now, let yfinance handle it, it might return what it can or default to a shorter period.
                elif delta_days > 60 : # For other intraday intervals like 5m, 15m, 30m, 1h
                     print(f"Warning: yfinance intraday data for interval {yf_interval} is typically limited to 60 days. Requested: {delta_days} days. This may fail or return limited data.")


            data = ticker.history(start=start_date_str, end=end_date_str, interval=yf_interval, proxy=proxy)

            if data.empty:
                print(f"YFinanceFetcher: No data found for {symbol} with the given parameters.")
                return pd.DataFrame() # Return empty DataFrame, consistent type

            # Standardize column names
            data.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            }, inplace=True)

            # Ensure index is datetime and timezone-aware (yfinance often returns tz-aware for some exchanges)
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index)

            # If index is timezone-aware, convert to UTC for consistency, or make naive.
            # For many strategies, naive local time of exchange is fine.
            # Let's make it naive for now, assuming operations will be on exchange time.
            if data.index.tz is not None:
                try:
                    # This can fail if mix of timezones or ambiguous times during DST transitions
                    data.index = data.index.tz_localize(None)
                except Exception as e:
                    print(f"YFinanceFetcher: Could not make index timezone naive for {symbol}: {e}. Using UTC.")
                    data.index = data.index.tz_convert('UTC').tz_localize(None)


            # Select only the required columns
            data = data[['open', 'high', 'low', 'close', 'volume']]

            # Some data like indices (e.g. ^NSEI for NIFTY 50) might not have volume. Fill with 0.
            if 'volume' not in data.columns or data['volume'].isnull().all():
                data['volume'] = 0
            data['volume'] = data['volume'].fillna(0).astype(int)


            print(f"YFinanceFetcher: Successfully fetched {len(data)} rows for {symbol}.")
            return data

        except Exception as e:
            print(f"YFinanceFetcher: Error fetching data for {symbol}: {e}")
            return pd.DataFrame() # Return empty DataFrame on error

    def get_current_price(self, symbol, proxy=None):
        """
        Fetches the current market price for a symbol.
        Note: This often uses the `info` dict or a very short `history` call.
        """
        try:
            ticker = yf.Ticker(symbol)
            # Using 'regularMarketPrice' or 'currentPrice' from info
            info = ticker.info
            price_keys = ['regularMarketPrice', 'currentPrice', 'previousClose'] # Order of preference
            for key in price_keys:
                if key in info and info[key] is not None:
                    print(f"YFinanceFetcher: Current price ({key}) for {symbol}: {info[key]}")
                    return info[key]

            # Fallback to last close if specific current price fields are missing
            data = ticker.history(period="1d", interval="1m", proxy=proxy) # Get very last known price
            if not data.empty:
                last_price = data['Close'].iloc[-1]
                print(f"YFinanceFetcher: Current price (last close) for {symbol}: {last_price}")
                return last_price

            print(f"YFinanceFetcher: Could not determine current price for {symbol} from info or history.")
            return None
        except Exception as e:
            print(f"YFinanceFetcher: Error fetching current price for {symbol}: {e}")
            return None

if __name__ == '__main__':
    fetcher = YFinanceFetcher()

    # Example usage:
    symbol_equity = "RELIANCE.NS" # NSE, India
    symbol_crypto = "BTC-USD"   # Crypto
    symbol_index = "^NSEI"      # NIFTY 50 Index

    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d') # Approx 2 months ago
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n--- Testing {symbol_equity} ---")
    data_equity_15m = fetcher.get_historical_data(symbol_equity, "15m", start_date, end_date)
    if not data_equity_15m.empty:
        print(f"Data for {symbol_equity} (15m):\n", data_equity_15m.head())
        print(f"Tail:\n", data_equity_15m.tail())
    else:
        print(f"No data retrieved for {symbol_equity} (15m).")

    start_date_1m = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d') # Last 6 days for 1m
    data_equity_1m = fetcher.get_historical_data(symbol_equity, "1m", start_date_1m, end_date)
    if not data_equity_1m.empty:
        print(f"\nData for {symbol_equity} (1m):\n", data_equity_1m.head())
    else:
        print(f"No data retrieved for {symbol_equity} (1m).")


    print(f"\n--- Testing {symbol_crypto} ---")
    start_date_crypto = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    data_crypto_1h = fetcher.get_historical_data(symbol_crypto, "1h", start_date_crypto, end_date)
    if not data_crypto_1h.empty:
        print(f"Data for {symbol_crypto} (1h):\n", data_crypto_1h.head())
    else:
        print(f"No data retrieved for {symbol_crypto} (1h).")

    print(f"\n--- Testing {symbol_index} ---")
    start_date_index = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d') # 1 year for daily
    data_index_1d = fetcher.get_historical_data(symbol_index, "1d", start_date_index, end_date)
    if not data_index_1d.empty:
        print(f"Data for {symbol_index} (1d):\n", data_index_1d.head())
        # Check volume for index
        if 'volume' in data_index_1d.columns:
            print(f"Volume for {symbol_index} (first 5 days): \n{data_index_1d['volume'].head()}")
    else:
        print(f"No data retrieved for {symbol_index} (1d).")

    print(f"\n--- Testing Current Price ---")
    current_price_equity = fetcher.get_current_price(symbol_equity)
    print(f"Current price for {symbol_equity}: {current_price_equity}")

    current_price_crypto = fetcher.get_current_price(symbol_crypto)
    print(f"Current price for {symbol_crypto}: {current_price_crypto}")

    # Test case for a short period where 1m data should be available
    print(f"\n--- Testing short period 1m data for {symbol_equity} ---")
    short_start = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    short_end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') # yesterday
    data_short_1m = fetcher.get_historical_data(symbol_equity, "1m", short_start, short_end)
    if not data_short_1m.empty:
        print(f"Data for {symbol_equity} (1m) from {short_start} to {short_end}:\n", data_short_1m.head())
        print(f"Tail:\n", data_short_1m.tail())
    else:
        print(f"No data retrieved for {symbol_equity} (1m) for the short period.")

    print("\n--- Testing invalid symbol ---")
    data_invalid = fetcher.get_historical_data("INVALID_SYMBOL_XYZ", "1d", start_date, end_date)
    if data_invalid.empty:
        print("Correctly returned empty DataFrame for invalid symbol.")
    else:
        print("Error: Expected empty DataFrame for invalid symbol.")

    print("\n--- Testing timeframe not directly supported by yfinance (e.g., '3m') ---")
    # This will use '2m' as per current _map_timeframe logic
    data_3m_mapped = fetcher.get_historical_data(symbol_equity, "3m", start_date_1m, end_date)
    if not data_3m_mapped.empty:
        print(f"Data for {symbol_equity} (mapped from 3m to 2m):\n", data_3m_mapped.head())
        # Check interval of returned data if possible (index diff)
        if len(data_3m_mapped) > 1:
            print("Time difference between first two candles:", data_3m_mapped.index[1] - data_3m_mapped.index[0])
    else:
        print(f"No data retrieved for {symbol_equity} (mapped from 3m).")
