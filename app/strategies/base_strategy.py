from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """
    def __init__(self, strategy_name, params=None):
        """
        Initializes the base strategy.

        Args:
            strategy_name (str): The name of the strategy.
            params (dict, optional): Strategy-specific parameters.
        """
        self.strategy_name = strategy_name
        self.params = params if params is not None else {}
        self._validate_params()
        print(f"BaseStrategy '{self.strategy_name}' initialized with params: {self.params}")

    def _validate_params(self):
        """
        Placeholder for validating strategy-specific parameters.
        Subclasses should override this if they have required parameters.
        """
        # Example:
        # required_keys = ['length', 'threshold']
        # if not all(key in self.params for key in required_keys):
        #     raise ValueError(f"Missing required parameters for {self.strategy_name}. Required: {required_keys}")
        pass

    def set_params(self, params):
        """
        Updates the strategy parameters and re-validates them.
        """
        self.params.update(params)
        self._validate_params()
        print(f"BaseStrategy '{self.strategy_name}' params updated: {self.params}")

    @abstractmethod
    def heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Converts standard OHLCV DataFrame to Heikin Ashi DataFrame.
        This might be a utility function or part of a strategy if it specifically uses HA candles.
        If it's a common utility, it could also live outside the strategy class.
        For now, keeping it here as it's a requirement for NovaV2.

        Args:
            df (pd.DataFrame): Input DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.

        Returns:
            pd.DataFrame: DataFrame with Heikin Ashi candles ('HA_Open', 'HA_High', 'HA_Low', 'HA_Close').
                          Original columns might be kept or dropped based on implementation.
        """
        pass

    @abstractmethod
    def generate_signals(self, df_primary: pd.DataFrame, df_higher_tf: pd.DataFrame = None) -> list:
        """
        Generates trading signals based on the strategy logic.

        Args:
            df_primary (pd.DataFrame): Primary timeframe market data (OHLCV or Heikin Ashi).
            df_higher_tf (pd.DataFrame, optional): Higher timeframe market data for confirmation.

        Returns:
            list: A list of dictionaries, where each dictionary represents a signal.
                  Example signal dict:
                  {
                      'timestamp': pd.Timestamp,
                      'signal_type': 'BUY' | 'SELL' | 'HOLD',
                      'entry_price': float, (optional)
                      'sl_price': float, (optional)
                      'tp1': float, (optional)
                      'tp2': float, (optional)
                      'tp3': float, (optional)
                      'atr_value': float, (optional, for strategies like NovaV2)
                      'details': dict (any other relevant info, e.g., indicator values)
                  }
        """
        pass

    def get_default_params(self) -> dict:
        """
        Returns the default parameters for the strategy.
        Subclasses should override this to provide their specific defaults.
        """
        return {}

    def __str__(self):
        return f"{self.strategy_name} Strategy (Parameters: {self.params})"

if __name__ == '__main__':
    # Example of how a subclass might look (won't run directly without implementation)
    class MyDummyStrategy(BaseStrategy):
        def __init__(self, params=None):
            super().__init__("DummyStrategy", params)
            # self.default_params = {'period': 14, 'level': 70} # Example
            # self.params = {**self.default_params, **(params if params else {})}
            # self._validate_params()


        def _validate_params(self):
            if 'period' not in self.params or not isinstance(self.params['period'], int):
                raise ValueError("DummyStrategy requires 'period' (int) in params.")
            print("DummyStrategy params validated.")

        def heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
            print("Dummy Heikin Ashi conversion called.")
            # Simplified: In a real scenario, this would do the HA calculation.
            ha_df = df.copy()
            ha_df.rename(columns={'open':'HA_Open', 'high':'HA_High', 'low':'HA_Low', 'close':'HA_Close'}, inplace=True)
            return ha_df

        def generate_signals(self, df_primary: pd.DataFrame, df_higher_tf: pd.DataFrame = None) -> list:
            print(f"DummyStrategy generating signals with period: {self.params.get('period')}")
            signals = []
            if not df_primary.empty:
                # Example: Generate a BUY signal on the first data point
                signals.append({
                    'timestamp': df_primary.index[0],
                    'signal_type': 'BUY',
                    'entry_price': df_primary['close'].iloc[0],
                    'details': {'message': 'Dummy BUY signal'}
                })
            return signals

        def get_default_params(self) -> dict:
            return {'period': 14, 'level': 70}


    print("--- Testing BaseStrategy (via DummyStrategy) ---")

    # Test with default params (if any were set in Dummy, otherwise empty)
    try:
        dummy_strat_default = MyDummyStrategy() # Will fail if _validate_params expects something not in default
        print(dummy_strat_default)
    except ValueError as e:
        print(f"Error initializing with default params: {e}")

    # Test with specific params
    custom_params = {'period': 20, 'level': 65}
    dummy_strat_custom = MyDummyStrategy(params=custom_params)
    print(dummy_strat_custom)

    # Test set_params
    dummy_strat_custom.set_params({'period': 25, 'new_param': 100}) # new_param won't be validated by current dummy
    print(dummy_strat_custom)

    # Test generating signals (requires a dummy DataFrame)
    sample_data = {
        'open': [10, 11, 12], 'high': [10.5, 11.5, 12.5],
        'low': [9.5, 10.5, 11.5], 'close': [10.2, 11.2, 12.2],
        'volume': [100, 110, 120]
    }
    sample_df = pd.DataFrame(sample_data, index=pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']))

    ha_df_dummy = dummy_strat_custom.heikin_ashi(sample_df.copy())
    print("\nDummy HA DataFrame Head:\n", ha_df_dummy.head())

    signals_dummy = dummy_strat_custom.generate_signals(sample_df)
    print("\nDummy Signals Generated:", signals_dummy)

    # Test get_default_params
    print("\nDefault params for DummyStrategy:", dummy_strat_custom.get_default_params())

    # Test validation failure
    try:
        print("\nTesting invalid params for DummyStrategy:")
        invalid_params = {'level': 50} # Missing 'period'
        dummy_strat_invalid = MyDummyStrategy(params=invalid_params)
    except ValueError as e:
        print(f"Correctly caught ValueError: {e}")

    try:
        print("\nTesting invalid param type for DummyStrategy:")
        invalid_type_params = {'period': 'abc'} # 'period' should be int
        dummy_strat_invalid_type = MyDummyStrategy(params=invalid_type_params)
    except ValueError as e:
        print(f"Correctly caught ValueError: {e}")

    print("BaseStrategy tests completed.")
