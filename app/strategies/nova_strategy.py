import pandas as pd
import numpy as np
import pandas_ta as ta # For ATR, EMA, SMA calculations

from .base_strategy import BaseStrategy

class NovaStrategy(BaseStrategy):
    """
    Implements the Nova V2 trading strategy based on the provided Pine Script logic.
    """
    def __init__(self, params=None):
        """
        Initializes the NovaV2 strategy.

        Default Parameters (from Pine Script and schema):
            length (int): EMA length for trend calculation (default: 6).
            target_offset (int): Offset for target calculation multiples (PineScript: target, default: 0).
            atr_period (int): Period for ATR calculation (PineScript: ta.atr(50), default: 50).
            atr_sma_period (int): Period for SMA of ATR (PineScript: ta.sma(atr, 50), default: 50).
            atr_multiplier (float): Multiplier for ATR value in bands (PineScript: * 0.8, default: 0.8).
        """
        default_params = self.get_default_params()
        strategy_params = {**default_params, **(params if params is not None else {})}
        super().__init__("NovaV2", strategy_params)

    def get_default_params(self) -> dict:
        return {
            'length': 6,
            'target_offset': 0, # This was 'target' in PineScript, renamed for clarity
            'atr_period': 50,
            'atr_sma_period': 50,
            'atr_multiplier': 0.8,
            # Optional: 'primary_timeframe', 'secondary_timeframes' can be managed by the app
            # but not directly used in core signal generation maths here unless explicitly passed.
        }

    def _validate_params(self):
        required_keys_types = {
            'length': int,
            'target_offset': int,
            'atr_period': int,
            'atr_sma_period': int,
            'atr_multiplier': float
        }
        for key, expected_type in required_keys_types.items():
            if key not in self.params:
                raise ValueError(f"Missing required parameter '{key}' for NovaStrategy.")
            if not isinstance(self.params[key], expected_type):
                # Allow int for float if it's a whole number, e.g. atr_multiplier=1
                if expected_type == float and isinstance(self.params[key], int):
                    self.params[key] = float(self.params[key]) # Coerce
                else:
                    raise ValueError(f"Parameter '{key}' must be of type {expected_type.__name__}, got {type(self.params[key]).__name__}.")
        if self.params['length'] <= 0: raise ValueError("Parameter 'length' must be positive.")
        if self.params['atr_period'] <= 0: raise ValueError("Parameter 'atr_period' must be positive.")
        if self.params['atr_sma_period'] <= 0: raise ValueError("Parameter 'atr_sma_period' must be positive.")


    def heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Converts standard OHLCV DataFrame to Heikin Ashi DataFrame.
        Uses pandas_ta for a robust implementation if available, otherwise manual.
        """
        if df.empty:
            return pd.DataFrame()

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Input DataFrame for Heikin Ashi must contain {required_cols}")

        # Using pandas_ta for Heikin Ashi
        try:
            ha_df = df.ta.ha() # pandas_ta directly adds HA_open, HA_high, HA_low, HA_close
            # Rename to match what strategy might expect or for consistent plotting
            ha_df.rename(columns={
                'HA_open': 'open', 'HA_high': 'high',
                'HA_low': 'low', 'HA_close': 'close'
            }, inplace=True)
            # Keep original volume if present
            if 'volume' in df.columns:
                ha_df['volume'] = df['volume']
            return ha_df[['open', 'high', 'low', 'close'] + (['volume'] if 'volume' in ha_df.columns else [])]

        except Exception as e: # Fallback or if pandas_ta not used as intended
            print(f"Pandas_ta Heikin Ashi failed: {e}. Using manual calculation.")
            ha_df = pd.DataFrame(index=df.index)
            ha_df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0

            ha_df['HA_Open'] = np.nan
            # First HA_Open is just the regular open
            if len(df) > 0:
                 ha_df.iloc[0, ha_df.columns.get_loc('HA_Open')] = df['open'].iloc[0]
            for i in range(1, len(df)):
                ha_df.iloc[i, ha_df.columns.get_loc('HA_Open')] = \
                    (ha_df['HA_Open'].iloc[i-1] + ha_df['HA_Close'].iloc[i-1]) / 2.0

            ha_df['HA_High'] = ha_df[['HA_Open', 'HA_Close']].join(df['high']).max(axis=1)
            ha_df['HA_Low'] = ha_df[['HA_Open', 'HA_Close']].join(df['low']).min(axis=1)

            # Rename for consistency
            ha_df.rename(columns={
                'HA_Open': 'open', 'HA_High': 'high',
                'HA_Low': 'low', 'HA_Close': 'close'
            }, inplace=True)
            if 'volume' in df.columns:
                ha_df['volume'] = df['volume']
            return ha_df


    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates all necessary indicators for the NovaV2 strategy.
        The input DataFrame `df` is assumed to be standard OHLC, not Heikin Ashi yet.
        The strategy determines trend on standard OHLC, then colors HA candles.
        """
        if df.empty:
            return pd.DataFrame()

        data = df.copy()

        # ATR معدّل للفريم القصير (ATR modified for short frame)
        # atr_value = ta.sma(ta.atr(50), 50) * 0.8
        data['atr'] = data.ta.atr(length=self.params['atr_period'])
        data['atr_sma'] = data.ta.sma(close=data['atr'], length=self.params['atr_sma_period'])
        data['atr_value'] = data['atr_sma'] * self.params['atr_multiplier']

        # المتوسطات المتحركة المعدّلة (Modified moving averages)
        # sma_high = ta.ema(high, length) + atr_value
        # sma_low  = ta.ema(low, length) - atr_value
        data['ema_high'] = data.ta.ema(close=data['high'], length=self.params['length'])
        data['ema_low'] = data.ta.ema(close=data['low'], length=self.params['length'])

        data['sma_high_band'] = data['ema_high'] + data['atr_value']
        data['sma_low_band'] = data['ema_low'] - data['atr_value']

        return data

    def generate_signals(self, df_primary: pd.DataFrame, df_higher_tf: pd.DataFrame = None) -> list:
        """
        Generates trading signals based on the NovaV2 strategy logic.
        PineScript: if ta.crossover(close, sma_high) and barstate.isconfirmed -> trend := true
                    if ta.crossunder(close, sma_low) and barstate.isconfirmed -> trend := false
        `barstate.isconfirmed` means calculations are done on closed bars. pandas_ta typically does this.

        Args:
            df_primary (pd.DataFrame): Primary timeframe OHLCV data.
            df_higher_tf (pd.DataFrame, optional): Higher timeframe OHLCV data (currently not used by core NovaV2 logic).

        Returns:
            list: List of signal dictionaries.
        """
        if df_primary.empty:
            return []

        data = self._calculate_indicators(df_primary.copy())

        # Determine trend
        # Initialize trend column, default to NaN or previous trend
        data['trend_up'] = False # True if current trend is up

        # Conditions for trend change
        crossed_above_high_band = (data['close'] > data['sma_high_band']) & (data['close'].shift(1) <= data['sma_high_band'].shift(1))
        crossed_below_low_band = (data['close'] < data['sma_low_band']) & (data['close'].shift(1) >= data['sma_low_band'].shift(1))

        # Iterate to set trend state (PineScript's `var bool trend = na` behavior)
        # This iterative approach mimics how `trend` persists in PineScript.
        current_trend_is_up = None # Can be True (up), False (down), None (undetermined initially)

        for i in range(len(data)):
            if current_trend_is_up is None: # Initial state or after trend was na
                if crossed_above_high_band.iloc[i]:
                    current_trend_is_up = True
                elif crossed_below_low_band.iloc[i]:
                    current_trend_is_up = False
            else: # Trend is already determined
                if current_trend_is_up: # Currently in uptrend
                    if crossed_below_low_band.iloc[i]: # Crossed below sma_low_band, trend flips to down
                        current_trend_is_up = False
                else: # Currently in downtrend
                    if crossed_above_high_band.iloc[i]: # Crossed above sma_high_band, trend flips to up
                        current_trend_is_up = True

            if current_trend_is_up is not None:
                data.loc[data.index[i], 'trend_up'] = current_trend_is_up
            elif i > 0 : # Propagate last known trend if no cross
                 data.loc[data.index[i], 'trend_up'] = data.loc[data.index[i-1], 'trend_up']


        # Identify signals (change in trend)
        # signal_up = ta.change(trend) and not trend[1] (trend was false, now true)
        # signal_down = ta.change(trend) and trend[1] (trend was true, now false)
        data['prev_trend_up'] = data['trend_up'].shift(1)

        # A buy signal occurs if trend was previously false (or NaN becoming true) and is now true.
        signal_up = (data['trend_up'] == True) & (data['prev_trend_up'] == False)
        # A sell signal occurs if trend was previously true (or NaN becoming false) and is now false.
        signal_down = (data['trend_up'] == False) & (data['prev_trend_up'] == True)

        signals_list = []
        target_offset = self.params['target_offset']

        for i in range(len(data)):
            signal_details = {
                'timestamp': data.index[i],
                'atr_value_at_signal': data['atr_value'].iloc[i], # Store this for reference
                'sma_low_band_at_signal': data['sma_low_band'].iloc[i],
                'sma_high_band_at_signal': data['sma_high_band'].iloc[i],
                'close_at_signal': data['close'].iloc[i],
                'details': {} # For any extra info like indicator values
            }

            if signal_up.iloc[i]:
                entry_price = data['close'].iloc[i]
                # Stop loss is sma_low_band at signal bar for BUY
                sl_price = data['sma_low_band'].iloc[i]

                # Targets are based on ATR multiples from entry_price
                # Pine: atr_multiplier * (4 + target), atr_multiplier * (8 + target * 2), ...
                # Here, atr_value already includes the 0.8 multiplier.
                # So, target_len1 = (current_atr_value / 0.8) * (4 + target_offset) * 0.8 = current_atr_value * (4 + target_offset)
                # This interpretation matches the PineScript intent of using the scaled ATR for target steps.
                current_atr = data['atr_value'].iloc[i] # This is already ATR * 0.8

                tp1 = entry_price + current_atr * (4 + target_offset)
                tp2 = entry_price + current_atr * (8 + target_offset * 2)
                tp3 = entry_price + current_atr * (12 + target_offset * 3)

                signals_list.append({
                    **signal_details,
                    'signal_type': 'BUY',
                    'entry_price': entry_price,
                    'sl_price': sl_price,
                    'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
                })

            elif signal_down.iloc[i]:
                entry_price = data['close'].iloc[i]
                # Stop loss is sma_high_band at signal bar for SELL
                sl_price = data['sma_high_band'].iloc[i]

                current_atr = data['atr_value'].iloc[i]

                tp1 = entry_price - current_atr * (4 + target_offset)
                tp2 = entry_price - current_atr * (8 + target_offset * 2)
                tp3 = entry_price - current_atr * (12 + target_offset * 3)

                signals_list.append({
                    **signal_details,
                    'signal_type': 'SELL',
                    'entry_price': entry_price,
                    'sl_price': sl_price,
                    'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
                })

        # Store calculated data for potential plotting or debugging by UI (optional)
        self.debug_data = data # Store the dataframe with all calculations

        return signals_list

    def get_plotting_data(self, df_ohlc: pd.DataFrame):
        """
        Helper function to get data necessary for plotting the strategy indicators.
        Returns a DataFrame with OHLC, Heikin Ashi, bands, and trend.
        """
        if df_ohlc.empty:
            return pd.DataFrame()

        # 1. Calculate indicators on OHLC data
        data_with_indicators = self._calculate_indicators(df_ohlc.copy())

        # 2. Determine trend (re-run trend logic from generate_signals for consistency)
        data_with_indicators['trend_up'] = False # True if current trend is up
        crossed_above_high_band = (data_with_indicators['close'] > data_with_indicators['sma_high_band']) & \
                                  (data_with_indicators['close'].shift(1) <= data_with_indicators['sma_high_band'].shift(1))
        crossed_below_low_band = (data_with_indicators['close'] < data_with_indicators['sma_low_band']) & \
                                 (data_with_indicators['close'].shift(1) >= data_with_indicators['sma_low_band'].shift(1))

        current_trend_is_up = None
        for i in range(len(data_with_indicators)):
            if current_trend_is_up is None:
                if crossed_above_high_band.iloc[i]: current_trend_is_up = True
                elif crossed_below_low_band.iloc[i]: current_trend_is_up = False
            else:
                if current_trend_is_up and crossed_below_low_band.iloc[i]: current_trend_is_up = False
                elif not current_trend_is_up and crossed_above_high_band.iloc[i]: current_trend_is_up = True

            if current_trend_is_up is not None:
                data_with_indicators.loc[data_with_indicators.index[i], 'trend_up'] = current_trend_is_up
            elif i > 0:
                 data_with_indicators.loc[data_with_indicators.index[i], 'trend_up'] = data_with_indicators.loc[data_with_indicators.index[i-1], 'trend_up']


        # 3. Generate Heikin Ashi candles from original OHLC
        # The Pine Script plots HA candles colored by the trend determined from normal candles.
        df_ha = self.heikin_ashi(df_ohlc.copy())

        # Combine: Use HA candles, add bands and trend from indicator calculations
        plot_df = df_ha.copy()
        plot_df['sma_high_band'] = data_with_indicators['sma_high_band']
        plot_df['sma_low_band'] = data_with_indicators['sma_low_band']
        plot_df['trend_up'] = data_with_indicators['trend_up']

        # Add original OHLC for reference if needed by plotter
        plot_df['original_open'] = df_ohlc['open']
        plot_df['original_high'] = df_ohlc['high']
        plot_df['original_low'] = df_ohlc['low']
        plot_df['original_close'] = df_ohlc['close']
        if 'volume' in df_ohlc.columns:
             plot_df['original_volume'] = df_ohlc['volume']


        return plot_df


if __name__ == '__main__':
    print("--- Testing NovaStrategy ---")

    # Create sample OHLCV data
    sample_ohlc_data = {
        'open':   [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 108, 106, 105, 107, 109, 111, 110, 108, 109],
        'high':   [103, 104, 103, 106, 107, 106, 108, 110, 109, 111, 112, 110, 108, 107, 110, 111, 112, 111, 110, 111],
        'low':    [99,  101, 100, 102, 104, 103, 105, 107, 106, 108, 109, 107, 105, 104, 106, 108, 110, 109, 107, 108],
        'close':  [102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 108, 106, 105, 107, 109, 111, 110, 108, 109, 110],
        'volume': [1000,1050,950, 1100,1150,1050,1200,1250,1150,1300,1350,1250,1150,1050,1200,1250,1300,1250,1150,1200]
    }
    index = pd.date_range(start='2023-01-01', periods=len(sample_ohlc_data['open']), freq='15min')
    df_sample = pd.DataFrame(sample_ohlc_data, index=index)

    # Initialize strategy
    nova_params = {'length': 6, 'target_offset': 0, 'atr_period': 5, 'atr_sma_period': 5, 'atr_multiplier': 0.8} # Smaller ATR periods for small dataset
    strategy = NovaStrategy(params=nova_params)
    print(f"Strategy initialized: {strategy}")

    # Test Heikin Ashi conversion
    print("\n--- Heikin Ashi Conversion Test ---")
    df_ha_test = strategy.heikin_ashi(df_sample.copy())
    if not df_ha_test.empty:
        print("Heikin Ashi DataFrame head:")
        print(df_ha_test.head())
    else:
        print("Heikin Ashi DataFrame is empty.")

    # Test indicator calculation (internal method, but can be exposed for testing)
    print("\n--- Indicator Calculation Test ---")
    df_with_indicators = strategy._calculate_indicators(df_sample.copy())
    if not df_with_indicators.empty:
        print("DataFrame with indicators (tail):")
        print(df_with_indicators[['close', 'atr_value', 'sma_high_band', 'sma_low_band']].tail())
    else:
        print("DataFrame with indicators is empty.")

    # Test signal generation
    print("\n--- Signal Generation Test ---")
    signals = strategy.generate_signals(df_sample.copy())
    if signals:
        print(f"Generated {len(signals)} signals:")
        for s in signals:
            print(f"  {s['timestamp']} - {s['signal_type']}: Entry={s.get('entry_price', 'N/A'):.2f}, SL={s.get('sl_price', 'N/A'):.2f}, TP1={s.get('tp1', 'N/A'):.2f}")
    else:
        print("No signals generated.")

    # Test get_plotting_data
    print("\n--- Plotting Data Generation Test ---")
    df_plot = strategy.get_plotting_data(df_sample.copy())
    if not df_plot.empty:
        print("Plotting DataFrame head (HA candles with bands and trend):")
        print(df_plot[['open', 'high', 'low', 'close', 'sma_low_band', 'sma_high_band', 'trend_up']].head())
        print("\nPlotting DataFrame tail:")
        print(df_plot[['open', 'high', 'low', 'close', 'sma_low_band', 'sma_high_band', 'trend_up']].tail())

    else:
        print("Plotting DataFrame is empty.")

    print("\n--- Testing with default params from strategy itself ---")
    strategy_default = NovaStrategy() # Uses get_default_params()
    signals_default = strategy_default.generate_signals(df_sample.copy())
    if signals_default:
        print(f"Generated {len(signals_default)} signals with default params.")
    else:
        print("No signals generated with default params.")

    print("\nNovaStrategy tests completed.")
