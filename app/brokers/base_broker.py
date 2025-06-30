from abc import ABC, abstractmethod
import pandas as pd

class BaseBroker(ABC):
    """
    Abstract base class for all broker interfaces.
    """
    def __init__(self, broker_name, params=None):
        self.broker_name = broker_name
        self.params = params if params is not None else {}
        self.is_connected = False
        print(f"BaseBroker '{self.broker_name}' initialized.")

    @abstractmethod
    def connect(self, **kwargs):
        """
        Establishes a connection to the broker.
        kwargs can include API keys, secrets, tokens, etc.
        Should set self.is_connected = True on success.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Closes the connection to the broker.
        Should set self.is_connected = False.
        """
        pass

    @abstractmethod
    def get_account_balance(self):
        """
        Retrieves account balance information.

        Returns:
            dict: A dictionary containing balance details (e.g., {'total_cash': 10000, 'margin_available': 5000}).
                  Returns None or raises an error if fetching fails.
        """
        pass

    @abstractmethod
    def get_positions(self):
        """
        Retrieves current open positions.

        Returns:
            list: A list of dictionaries, where each dict represents a position.
                  Example: [{'symbol': 'RELIANCE.NS', 'quantity': 10, 'average_price': 2500.00, 'ltp': 2510.00}]
                  Returns empty list or None if no positions or error.
        """
        pass

    @abstractmethod
    def get_orders(self, order_id=None):
        """
        Retrieves order history or status of a specific order.

        Args:
            order_id (str, optional): If provided, fetches status for this specific order.
                                     Otherwise, may fetch recent/all open orders.
        Returns:
            list/dict: Depending on implementation, a list of order objects or a single order object.
                       Example order object: {'order_id': '123', 'symbol': 'TCS.NS', 'status': 'FILLED', ...}
        """
        pass

    @abstractmethod
    def place_order(self, symbol: str, transaction_type: str, quantity: float,
                    order_type: str, price: float = None, trigger_price: float = None,
                    product_type: str = "MIS", exchange: str = "NSE", **kwargs) -> dict:
        """
        Places an order with the broker.

        Args:
            symbol (str): Trading symbol (e.g., "RELIANCE-EQ" for Fyers, "RELIANCE.NS" for yfinance/some UIs).
                          Broker interface should handle symbol mapping if needed.
            transaction_type (str): "BUY" or "SELL".
            quantity (float): Number of shares/contracts.
            order_type (str): "MARKET", "LIMIT", "SL", "SL-M".
            price (float, optional): Required for LIMIT and SL orders.
            trigger_price (float, optional): Required for SL and SL-M orders.
            product_type (str): Product type (e.g., "MIS", "CNC", "NRML"). Default "MIS".
            exchange (str): Exchange code (e.g., "NSE", "BSE", "NFO"). Default "NSE".
            **kwargs: Additional broker-specific parameters.

        Returns:
            dict: A dictionary containing order placement status, including an 'order_id' on success.
                  Example: {'status': 'success', 'order_id': 'xyz123', 'message': 'Order placed'}
                           {'status': 'error', 'message': 'Insufficient funds'}
        """
        pass

    @abstractmethod
    def modify_order(self, order_id: str, new_quantity: float = None, new_price: float = None,
                     new_trigger_price: float = None, new_order_type: str = None, **kwargs) -> dict:
        """
        Modifies an existing pending order.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, **kwargs) -> dict:
        """
        Cancels an existing pending order.
        """
        pass

    def paper_trade(self, signal: dict, current_market_data: pd.Series = None, account_balance: dict = None) -> dict:
        """
        Simulates the execution of a trading signal without real money.
        This is a default implementation that can be overridden by subclasses if they have more sophisticated paper trading.

        Args:
            signal (dict): A signal dictionary from a strategy. Expected keys:
                           'timestamp', 'signal_type' ('BUY'/'SELL'), 'entry_price' (target entry),
                           'sl_price', 'tp1', 'tp2', 'tp3'.
                           'instrument_id' or 'symbol' should also be available or passed.
            current_market_data (pd.Series, optional): Series representing the current candle's OHLCV data
                                                       at which the signal is being evaluated for paper trading.
                                                       If None, signal['entry_price'] is assumed as fill price.
            account_balance (dict, optional): Current paper trading account balance for risk checks.

        Returns:
            dict: An execution record dictionary, similar to what `broker_executions` table expects.
                  Example: {'signal_id': ..., 'broker_order_id': 'PAPER_XYZ', 'timestamp': ...,
                            'filled_price': ..., 'quantity': ..., 'status': 'FILLED', ...}
        """
        print(f"PaperTrading ({self.broker_name}): Simulating signal: {signal.get('signal_type')} for {signal.get('symbol', signal.get('instrument_id'))}")

        # Determine fill price: Use current close if available, else signal's entry price
        fill_price = signal.get('entry_price')
        if current_market_data is not None and not current_market_data.empty:
            # Simulate fill based on signal type and current market conditions (e.g., next bar open, or within current bar's range)
            # For simplicity, let's assume it fills at the suggested entry_price if within current bar's H/L range,
            # or at current_market_data['close'] if entry_price is too far.
            # A more realistic simulation would use next bar's open or a slippage model.
            if signal.get('signal_type') == 'BUY':
                if signal.get('entry_price') >= current_market_data['low']: # Can buy at or better than entry
                    fill_price = min(signal.get('entry_price'), current_market_data['high']) # Assume best case within bar
                else: # Entry price missed, fill at close or don't fill
                    fill_price = current_market_data['close'] # Or mark as missed
            elif signal.get('signal_type') == 'SELL':
                if signal.get('entry_price') <= current_market_data['high']: # Can sell at or better than entry
                    fill_price = max(signal.get('entry_price'), current_market_data['low']) # Assume best case
                else:
                    fill_price = current_market_data['close']

        # Simplified quantity: 1 unit for now. Real implementation would use risk management.
        quantity = 1.0
        # Risk management example (conceptual):
        # if account_balance and signal.get('sl_price'):
        #     risk_per_share = abs(fill_price - signal['sl_price'])
        #     if risk_per_share > 0:
        #         total_risk_allowed = account_balance.get('total_cash', 100000) * 0.02 # 2% risk
        #         quantity = total_risk_allowed / risk_per_share
        #         quantity = max(1.0, round(quantity)) # Ensure at least 1, round appropriately

        execution_record = {
            'signal_id': signal.get('id'), # If signal is already saved and has an ID
            'broker_order_id': f"PAPER_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}",
            'parent_order_id': None,
            'instrument_id': signal.get('instrument_id'), # Important for linking
            'timestamp': pd.Timestamp.now(), # Execution time
            'order_type': 'MARKET', # Paper trades usually simulated as market orders
            'transaction_type': signal.get('signal_type'),
            'filled_price': fill_price,
            'average_price': fill_price,
            'quantity': quantity,
            'trigger_price': None,
            'status': 'COMPLETE', # Or 'FILLED' if using broker enum strictly
            'broker_name': f"{self.broker_name}_Paper",
            'broker_response': {'message': 'Paper trade simulated successfully.'},
            'tags': 'PaperTrade, Entry'
        }
        print(f"PaperTrading ({self.broker_name}): Simulated execution: {execution_record}")
        return execution_record


if __name__ == '__main__':
    # This class is abstract and cannot be instantiated directly.
    # Example of how a subclass might look:

    class MyMockBroker(BaseBroker):
        def __init__(self, params=None):
            super().__init__("MockBroker", params)
            self.mock_balance = {'total_cash': 100000, 'margin_available': 100000}
            self.mock_positions = []
            self.mock_orders = {}

        def connect(self, api_key="test_key", secret="test_secret"):
            print(f"{self.broker_name}: Connecting with key {api_key[:4]}...")
            self.is_connected = True
            print(f"{self.broker_name}: Connected successfully.")
            return True

        def disconnect(self):
            print(f"{self.broker_name}: Disconnecting...")
            self.is_connected = False
            print(f"{self.broker_name}: Disconnected.")

        def get_account_balance(self):
            if not self.is_connected: raise ConnectionError("Not connected")
            return self.mock_balance

        def get_positions(self):
            if not self.is_connected: raise ConnectionError("Not connected")
            return self.mock_positions

        def get_orders(self, order_id=None):
            if not self.is_connected: raise ConnectionError("Not connected")
            if order_id:
                return self.mock_orders.get(order_id)
            return list(self.mock_orders.values())

        def place_order(self, symbol: str, transaction_type: str, quantity: float,
                        order_type: str, price: float = None, trigger_price: float = None,
                        product_type: str = "MIS", exchange: str = "NSE", **kwargs) -> dict:
            if not self.is_connected: raise ConnectionError("Not connected")
            order_id = f"mock_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}"
            order_details = {
                'order_id': order_id, 'symbol': symbol, 'transaction_type': transaction_type,
                'quantity': quantity, 'order_type': order_type, 'price': price,
                'trigger_price': trigger_price, 'status': 'PENDING_OPEN', # Simulate pending initially
                'timestamp': pd.Timestamp.now()
            }
            self.mock_orders[order_id] = order_details
            print(f"{self.broker_name}: Order placed: {order_id} for {symbol}")
            # Simulate it getting filled quickly for testing paper_trade or other flows
            order_details['status'] = 'COMPLETE'
            order_details['filled_price'] = price if order_type == "LIMIT" else (100.0 if transaction_type == "BUY" else 99.0) # Mock fill price

            # Update mock positions (simplified)
            existing_pos = next((p for p in self.mock_positions if p['symbol'] == symbol), None)
            if existing_pos:
                if transaction_type == "BUY": existing_pos['quantity'] += quantity
                else: existing_pos['quantity'] -= quantity
                if existing_pos['quantity'] == 0: self.mock_positions.remove(existing_pos)
            elif transaction_type == "BUY":
                self.mock_positions.append({'symbol': symbol, 'quantity': quantity, 'average_price': order_details['filled_price']})
            # Add handling for SELL (shorting) if needed for your mock

            return {'status': 'success', 'order_id': order_id, 'message': 'Mock order placed and filled.'}

        def modify_order(self, order_id: str, **kwargs) -> dict:
            if not self.is_connected: raise ConnectionError("Not connected")
            if order_id in self.mock_orders:
                print(f"{self.broker_name}: Modifying order {order_id} (mock).")
                # self.mock_orders[order_id].update(kwargs) # Basic update
                return {'status': 'success', 'order_id': order_id, 'message': 'Mock order modified.'}
            return {'status': 'error', 'message': 'Order not found.'}

        def cancel_order(self, order_id: str, **kwargs) -> dict:
            if not self.is_connected: raise ConnectionError("Not connected")
            if order_id in self.mock_orders:
                print(f"{self.broker_name}: Cancelling order {order_id} (mock).")
                self.mock_orders[order_id]['status'] = 'CANCELLED'
                return {'status': 'success', 'order_id': order_id, 'message': 'Mock order cancelled.'}
            return {'status': 'error', 'message': 'Order not found.'}

    print("--- Testing BaseBroker (via MyMockBroker) ---")
    broker = MyMockBroker()
    broker.connect()

    print("\nAccount Balance:", broker.get_account_balance())

    print("\nPlacing BUY order...")
    buy_order = broker.place_order("RELIANCE.NS", "BUY", 10, "LIMIT", 2500.00)
    print("Buy Order Response:", buy_order)

    print("\nPositions:", broker.get_positions())
    print("\nOrders:", broker.get_orders())

    print("\nSimulating paper trade for a BUY signal:")
    buy_signal_example = {
        'id': 123, 'instrument_id': 1, 'symbol': 'RELIANCE.NS',
        'timestamp': pd.Timestamp.now(), 'signal_type': 'BUY',
        'entry_price': 2505.00, 'sl_price': 2480.00, 'tp1': 2550.00
    }
    # Mock current market data for paper trade simulation
    current_candle_data = pd.Series({
        'open': 2504.00, 'high': 2508.00, 'low': 2503.00, 'close': 2506.00, 'volume': 5000
    })
    paper_exec = broker.paper_trade(buy_signal_example, current_market_data=current_candle_data, account_balance=broker.get_account_balance())
    print("Paper Execution Record:", paper_exec)

    broker.disconnect()
    print("\nBaseBroker tests completed.")
