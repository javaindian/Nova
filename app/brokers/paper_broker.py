from .base_broker import BaseBroker
import pandas as pd
from datetime import datetime
import json

class PaperBroker(BaseBroker):
    """
    A simulated broker for paper trading.
    It maintains an internal state for account balance, positions, and orders.
    """
    def __init__(self, initial_balance=100000.0, params=None):
        super().__init__("PaperBroker", params)
        self.initial_balance = float(initial_balance)
        self.cash = float(initial_balance)
        self.positions = {}  # symbol: {'quantity': float, 'average_price': float, 'ltp': float, 'unrealized_pnl': float}
        self.orders = {}     # order_id: order_details_dict
        self.order_id_counter = 0
        self.trade_history = [] # List of executed trade dicts
        self.portfolio_value = float(initial_balance)
        self.margin_used = 0.0

        print(f"PaperBroker initialized with balance: {self.initial_balance}")

    def connect(self, **kwargs):
        print(f"{self.broker_name}: 'Connected'. Ready for paper trading.")
        self.is_connected = True
        return True

    def disconnect(self):
        print(f"{self.broker_name}: 'Disconnected'.")
        self.is_connected = False
        # Optionally, reset state or save final state here
        # self.reset_account()

    def reset_account(self, new_initial_balance=None):
        """Resets the paper trading account to its initial state or a new balance."""
        self.initial_balance = float(new_initial_balance) if new_initial_balance is not None else self.initial_balance
        self.cash = self.initial_balance
        self.positions = {}
        self.orders = {}
        self.order_id_counter = 0
        self.trade_history = []
        self.portfolio_value = self.initial_balance
        self.margin_used = 0.0
        print(f"PaperBroker account reset. New balance: {self.cash}")

    def get_account_balance(self):
        if not self.is_connected: raise ConnectionError("Not connected")
        self._update_portfolio_value() # Update based on current LTPs of positions
        return {
            'total_cash': self.cash,
            'portfolio_value': self.portfolio_value,
            'margin_available': self.cash, # Simplified: cash = available margin
            'margin_used': self.margin_used, # Basic margin placeholder
            'unrealized_pnl': self.portfolio_value - self.initial_balance - self._calculate_realized_pnl() # Conceptual
        }

    def _calculate_realized_pnl(self):
        # Conceptual: Sum PnL from closed trades in trade_history
        realized_pnl = 0
        # This would require trade_history to store PnL for each closed trade.
        # For now, this is a simplification.
        return realized_pnl

    def _update_ltp_for_positions(self, market_data_feed: dict = None):
        """
        Updates the LTP for all open positions.
        market_data_feed: {'SYMBOL1': current_price, 'SYMBOL2': current_price}
        """
        if market_data_feed:
            for symbol, pos_details in self.positions.items():
                if symbol in market_data_feed:
                    pos_details['ltp'] = market_data_feed[symbol]

    def _update_portfolio_value(self, market_data_feed: dict = None):
        """
        Recalculates portfolio value based on cash and current market value of positions.
        market_data_feed: {'SYMBOL1': current_price, 'SYMBOL2': current_price} for updating LTPs.
        """
        self._update_ltp_for_positions(market_data_feed)

        current_positions_value = 0
        for symbol, pos_details in self.positions.items():
            ltp = pos_details.get('ltp', pos_details['average_price']) # Use avg_price if LTP not updated
            current_positions_value += pos_details['quantity'] * ltp
            pos_details['unrealized_pnl'] = (ltp - pos_details['average_price']) * pos_details['quantity']

        self.portfolio_value = self.cash + current_positions_value
        return self.portfolio_value


    def get_positions(self, market_data_feed: dict = None):
        if not self.is_connected: raise ConnectionError("Not connected")
        self._update_portfolio_value(market_data_feed) # Ensure PnL and LTP are fresh

        # Convert internal positions dict to list of dicts format
        return [
            {'symbol': symbol, **details} for symbol, details in self.positions.items() if details['quantity'] != 0
        ]

    def get_orders(self, order_id=None):
        if not self.is_connected: raise ConnectionError("Not connected")
        if order_id:
            return self.orders.get(order_id)
        return list(self.orders.values()) # Return all orders

    def _generate_order_id(self):
        self.order_id_counter += 1
        return f"PAPER_{self.order_id_counter:06d}_{pd.Timestamp.now().strftime('%S%f')}"

    def place_order(self, symbol: str, transaction_type: str, quantity: float,
                    order_type: str, price: float = None, trigger_price: float = None,
                    product_type: str = "MIS", exchange: str = "NSE", current_ltp: float = None, **kwargs) -> dict:
        """
        Simulates placing an order.
        `current_ltp` is crucial for market order simulation.
        """
        if not self.is_connected: raise ConnectionError("Not connected")

        order_id = self._generate_order_id()
        timestamp = pd.Timestamp.now()

        # Determine fill price (simplified simulation)
        simulated_fill_price = None
        if order_type.upper() == "MARKET":
            if current_ltp is None:
                return {'status': 'error', 'order_id': order_id, 'message': 'Market order requires current_ltp for simulation.'}
            simulated_fill_price = current_ltp # Ideal fill at current market price
        elif order_type.upper() == "LIMIT":
            if price is None:
                return {'status': 'error', 'order_id': order_id, 'message': 'Limit order requires price.'}
            # Simulate fill if current_ltp crosses limit price (very basic)
            if current_ltp is not None:
                if transaction_type.upper() == "BUY" and current_ltp <= price:
                    simulated_fill_price = price
                elif transaction_type.upper() == "SELL" and current_ltp >= price:
                    simulated_fill_price = price
                else: # Limit order not met by current_ltp
                    order_details = {
                        'order_id': order_id, 'symbol': symbol, 'exchange': exchange, 'transaction_type': transaction_type,
                        'quantity': quantity, 'pending_quantity': quantity, 'filled_quantity': 0,
                        'order_type': order_type, 'price': price, 'trigger_price': trigger_price,
                        'status': 'PENDING_OPEN', 'timestamp': timestamp, 'product_type': product_type,
                        'filled_price': None, 'average_price': None
                    }
                    self.orders[order_id] = order_details
                    return {'status': 'success', 'order_id': order_id, 'message': 'Limit order placed, pending execution.'}
            else: # No current_ltp, cannot simulate limit fill easily
                 order_details = { # Assume it's pending
                        'order_id': order_id, 'symbol': symbol, 'exchange': exchange, 'transaction_type': transaction_type,
                        'quantity': quantity, 'pending_quantity': quantity, 'filled_quantity': 0,
                        'order_type': order_type, 'price': price, 'trigger_price': trigger_price,
                        'status': 'PENDING_OPEN', 'timestamp': timestamp, 'product_type': product_type,
                        'filled_price': None, 'average_price': None
                    }
                 self.orders[order_id] = order_details
                 return {'status': 'success', 'order_id': order_id, 'message': 'Limit order placed (LTP unknown, pending).'}

        elif order_type.upper() in ["SL", "SL-M"]:
            # SL orders are more complex to simulate without a feed; treat as pending.
            order_details = {
                'order_id': order_id, 'symbol': symbol, 'exchange': exchange, 'transaction_type': transaction_type,
                'quantity': quantity, 'pending_quantity': quantity, 'filled_quantity': 0,
                'order_type': order_type, 'price': price, 'trigger_price': trigger_price,
                'status': 'PENDING_OPEN', 'timestamp': timestamp, 'product_type': product_type,
                'filled_price': None, 'average_price': None
            }
            self.orders[order_id] = order_details
            return {'status': 'success', 'order_id': order_id, 'message': f'{order_type} order placed, pending trigger.'}
        else:
            return {'status': 'error', 'order_id': order_id, 'message': f'Unsupported order type for paper trading: {order_type}'}

        if simulated_fill_price is None: # Should not happen if logic above is complete for MARKET/LIMIT with LTP
            return {'status': 'error', 'order_id': order_id, 'message': 'Could not determine fill price for simulation.'}

        # Cost/Proceeds Calculation
        trade_value = simulated_fill_price * quantity

        # Basic Margin/Funds Check (conceptual)
        required_margin = trade_value * 0.2 # Example: 20% margin for MIS (very simplified)
        if transaction_type.upper() == "BUY":
            if self.cash < trade_value: # For CNC-like check
            # if self.cash < required_margin: # For margin product check
                return {'status': 'error', 'order_id': order_id, 'message': 'Insufficient funds for paper trade.'}
            self.cash -= trade_value
            self.margin_used += required_margin
        else: # SELL
            # Check if shorting is allowed or if position exists to sell
            if symbol not in self.positions or self.positions[symbol]['quantity'] < quantity:
                # Allow shorting for paper trading for now, adjust cash as if receiving proceeds.
                # A real broker would block if insufficient shares for non-short sell.
                print(f"PaperBroker: Short selling {quantity} of {symbol} or selling non-existent position.")
            self.cash += trade_value
            self.margin_used += required_margin # Margin for shorts too

        # Update Positions
        if symbol in self.positions:
            current_pos = self.positions[symbol]
            if transaction_type.upper() == "BUY":
                new_avg_price = ((current_pos['average_price'] * current_pos['quantity']) +
                                 (simulated_fill_price * quantity)) / (current_pos['quantity'] + quantity)
                current_pos['quantity'] += quantity
                current_pos['average_price'] = new_avg_price
            else: # SELL
                # Realized PnL for this part of sell if closing a position
                # For simplicity, just update quantity. PnL on full close.
                current_pos['quantity'] -= quantity
                if current_pos['quantity'] == 0: # Position closed
                    # Calculate realized PnL for this closing trade
                    realized_pnl_trade = (simulated_fill_price - current_pos['average_price']) * quantity
                    print(f"PaperBroker: Position closed for {symbol}. Realized PnL for this part: {realized_pnl_trade}")
                    # This PnL is already accounted for in cash adjustment.
                    del self.positions[symbol]
                # If quantity becomes negative, it's a short position.
        else: # New position
            if transaction_type.upper() == "BUY":
                self.positions[symbol] = {'quantity': quantity, 'average_price': simulated_fill_price, 'ltp': simulated_fill_price, 'unrealized_pnl': 0.0}
            else: # New SELL (short)
                self.positions[symbol] = {'quantity': -quantity, 'average_price': simulated_fill_price, 'ltp': simulated_fill_price, 'unrealized_pnl': 0.0}


        order_details = {
            'order_id': order_id, 'symbol': symbol, 'exchange': exchange, 'transaction_type': transaction_type,
            'quantity': quantity, 'pending_quantity': 0, 'filled_quantity': quantity,
            'order_type': order_type, 'price': price if order_type=="LIMIT" else simulated_fill_price,
            'trigger_price': trigger_price,
            'status': 'COMPLETE', 'timestamp': timestamp, 'product_type': product_type,
            'filled_price': simulated_fill_price, 'average_price': simulated_fill_price, # Avg price of THIS order
            'broker_response': {'message': 'Paper trade executed successfully.'}
        }
        self.orders[order_id] = order_details
        self.trade_history.append(order_details)
        self._update_portfolio_value({symbol: simulated_fill_price}) # Update portfolio with this trade's fill price

        return {'status': 'success', 'order_id': order_id, 'message': 'Paper order simulated as filled.', 'filled_price': simulated_fill_price, 'filled_quantity': quantity}

    def modify_order(self, order_id: str, new_quantity: float = None, new_price: float = None,
                     new_trigger_price: float = None, new_order_type: str = None, **kwargs) -> dict:
        if not self.is_connected: raise ConnectionError("Not connected")
        if order_id not in self.orders:
            return {'status': 'error', 'message': 'Order ID not found.'}

        order = self.orders[order_id]
        if order['status'] != 'PENDING_OPEN':
            return {'status': 'error', 'message': f'Cannot modify order in status: {order["status"]}.'}

        if new_quantity is not None: order['quantity'] = new_quantity; order['pending_quantity'] = new_quantity
        if new_price is not None: order['price'] = new_price
        if new_trigger_price is not None: order['trigger_price'] = new_trigger_price
        if new_order_type is not None: order['order_type'] = new_order_type
        order['timestamp'] = pd.Timestamp.now() # Update timestamp on modification
        print(f"PaperBroker: Order {order_id} modified. New details: {order}")
        return {'status': 'success', 'order_id': order_id, 'message': 'Paper order modified.'}

    def cancel_order(self, order_id: str, **kwargs) -> dict:
        if not self.is_connected: raise ConnectionError("Not connected")
        if order_id not in self.orders:
            return {'status': 'error', 'message': 'Order ID not found.'}

        order = self.orders[order_id]
        if order['status'] != 'PENDING_OPEN':
             return {'status': 'error', 'message': f'Cannot cancel order in status: {order["status"]}.'}

        order['status'] = 'CANCELLED'
        order['pending_quantity'] = 0
        order['timestamp'] = pd.Timestamp.now()
        print(f"PaperBroker: Order {order_id} cancelled.")
        return {'status': 'success', 'order_id': order_id, 'message': 'Paper order cancelled.'}

    def process_pending_orders(self, market_data_feed: dict):
        """
        Processes pending LIMIT and SL orders based on current market data.
        market_data_feed: {'SYMBOL': {'open':o, 'high':h, 'low':l, 'close':c, 'ltp':ltp}, ...}
        This needs to be called periodically by the trading loop.
        """
        if not self.is_connected: return

        executed_order_ids = []
        for order_id, order in list(self.orders.items()): # Iterate on copy for modification
            if order['status'] != 'PENDING_OPEN':
                continue

            symbol_data = market_data_feed.get(order['symbol'])
            if not symbol_data:
                continue # No current data for this symbol to process order

            # Current market prices for the symbol
            current_high = symbol_data.get('high', symbol_data.get('ltp')) # Fallback to ltp if H/L not present
            current_low = symbol_data.get('low', symbol_data.get('ltp'))
            current_ltp = symbol_data.get('ltp') # Last Traded Price is key

            if current_ltp is None: continue # Cannot process without LTP

            simulated_fill_price = None
            execute_now = False

            # LIMIT Order Logic
            if order['order_type'].upper() == "LIMIT":
                if order['transaction_type'].upper() == "BUY" and current_low <= order['price']: # Market moved down to or below limit price
                    simulated_fill_price = min(order['price'], current_high) # Filled at limit or better (current high of bar)
                    execute_now = True
                elif order['transaction_type'].upper() == "SELL" and current_high >= order['price']: # Market moved up to or above limit price
                    simulated_fill_price = max(order['price'], current_low) # Filled at limit or better (current low of bar)
                    execute_now = True

            # SL / SL-M Order Logic (simplified: trigger then treat as market)
            elif order['order_type'].upper() in ["SL", "SL-M"]:
                if order['transaction_type'].upper() == "BUY": # Buy SL (typically to cover short or enter on breakout)
                    if current_high >= order['trigger_price']:
                        simulated_fill_price = order['trigger_price'] if order['order_type'].upper() == "SL-M" else min(order['price'], current_high) if order['price'] else order['trigger_price'] # SL-Limit or SL-Market logic
                        execute_now = True
                elif order['transaction_type'].upper() == "SELL": # Sell SL (typically to stop loss on long or enter short on breakdown)
                    if current_low <= order['trigger_price']:
                        simulated_fill_price = order['trigger_price'] if order['order_type'].upper() == "SL-M" else max(order['price'], current_low) if order['price'] else order['trigger_price']
                        execute_now = True

            if execute_now and simulated_fill_price is not None:
                print(f"PaperBroker: Triggering execution for pending order {order_id} at {simulated_fill_price}")
                # Use the place_order logic for position and cash updates, but mark as triggered.
                # This is a bit recursive; ideally, have a separate _execute_trade method.
                # For now, directly update state:

                trade_value = simulated_fill_price * order['quantity']
                if order['transaction_type'].upper() == "BUY":
                    if self.cash < trade_value: # Simplified check
                        print(f"PaperBroker: Insufficient funds to execute pending BUY order {order_id}.")
                        continue # Skip this order for now
                    self.cash -= trade_value
                else: # SELL
                    self.cash += trade_value

                # Update Positions
                if order['symbol'] in self.positions:
                    pos = self.positions[order['symbol']]
                    new_avg = ((pos['average_price'] * pos['quantity']) + (simulated_fill_price * order['quantity'])) / (pos['quantity'] + order['quantity']) if (pos['quantity'] + order['quantity']) !=0 else simulated_fill_price
                    pos['quantity'] += order['quantity'] if order['transaction_type'].upper() == "BUY" else -order['quantity']
                    pos['average_price'] = new_avg
                    if pos['quantity'] == 0: del self.positions[order['symbol']]
                else:
                    qty_val = order['quantity'] if order['transaction_type'].upper() == "BUY" else -order['quantity']
                    self.positions[order['symbol']] = {'quantity': qty_val, 'average_price': simulated_fill_price, 'ltp': simulated_fill_price, 'unrealized_pnl':0.0}

                order['status'] = 'COMPLETE'
                order['filled_price'] = simulated_fill_price
                order['average_price'] = simulated_fill_price
                order['filled_quantity'] = order['quantity']
                order['pending_quantity'] = 0
                order['timestamp'] = pd.Timestamp.now() # Execution time
                self.trade_history.append(order.copy())
                executed_order_ids.append(order_id)
                self._update_portfolio_value({order['symbol']: simulated_fill_price})
                print(f"PaperBroker: Order {order_id} executed. New cash: {self.cash}, Portfolio: {self.portfolio_value}")

        return executed_order_ids


if __name__ == '__main__':
    print("--- Testing PaperBroker ---")
    paper_broker = PaperBroker(initial_balance=50000)
    paper_broker.connect()

    print("\nInitial Account State:")
    print(json.dumps(paper_broker.get_account_balance(), indent=2))
    print("Positions:", paper_broker.get_positions())

    print("\n--- Market Order Simulation ---")
    # Simulate placing a BUY MARKET order for 'TEST.NS' at current_ltp 100
    buy_market_resp = paper_broker.place_order("TEST.NS", "BUY", 10, "MARKET", current_ltp=100.0)
    print("Buy Market Order Response:", buy_market_resp)
    print("Account State after BUY:", json.dumps(paper_broker.get_account_balance(), indent=2))
    print("Positions after BUY:", paper_broker.get_positions(market_data_feed={'TEST.NS': 100.0}))

    # Simulate LTP change and check PnL
    print("\n--- LTP Update Simulation ---")
    paper_broker._update_portfolio_value(market_data_feed={'TEST.NS': 105.0}) # LTP goes up
    print("Account State after LTP up:", json.dumps(paper_broker.get_account_balance(), indent=2))
    print("Positions after LTP up:", paper_broker.get_positions()) # LTP should be 105

    # Simulate selling part of the position via MARKET order
    print("\n--- Partial Sell Market Order ---")
    sell_market_resp = paper_broker.place_order("TEST.NS", "SELL", 5, "MARKET", current_ltp=105.0)
    print("Sell Market Order Response:", sell_market_resp)
    print("Account State after SELL:", json.dumps(paper_broker.get_account_balance(), indent=2))
    print("Positions after SELL:", paper_broker.get_positions(market_data_feed={'TEST.NS': 105.0}))


    print("\n--- Limit Order Simulation ---")
    # Place a LIMIT BUY order for 'ANOTHER.NS' at 50, current_ltp is 52 (order should be pending)
    buy_limit_resp = paper_broker.place_order("ANOTHER.NS", "BUY", 20, "LIMIT", price=50.0, current_ltp=52.0)
    print("Buy Limit Order Response:", buy_limit_resp)
    limit_order_id = buy_limit_resp.get('order_id')
    print("Orderbook:", paper_broker.get_orders(limit_order_id))

    # Simulate market moving down, triggering the limit order
    print("\n--- Processing Pending Orders (LTP drops to 50) ---")
    market_update_feed = {"ANOTHER.NS": {'open':51,'high':51,'low':49.5,'close':50, 'ltp':50.0}}
    executed_ids = paper_broker.process_pending_orders(market_update_feed)
    print(f"Executed order IDs from pending: {executed_ids}")
    print("Orderbook after processing:", paper_broker.get_orders(limit_order_id))
    print("Positions after limit BUY:", paper_broker.get_positions(market_data_feed=market_update_feed))
    print("Account State:", json.dumps(paper_broker.get_account_balance(), indent=2))

    print("\n--- SL Order Simulation (conceptual) ---")
    # Place a SELL SL order for 'ANOTHER.NS' (which we hold 20 shares of at avg ~50)
    # Trigger at 48, Limit (if SL-L) at 47.5
    sl_sell_resp = paper_broker.place_order("ANOTHER.NS", "SELL", 20, "SL", price=47.5, trigger_price=48.0, current_ltp=50.0)
    print("Sell SL Order Response:", sl_sell_resp)
    sl_order_id = sl_sell_resp.get('order_id')
    print("Orderbook with SL:", paper_broker.get_orders(sl_order_id))

    print("\n--- Processing Pending Orders (LTP drops to trigger SL) ---")
    market_update_feed_sl = {"ANOTHER.NS": {'open':48.5,'high':48.5,'low':47.0,'close':47.2, 'ltp':47.2}} # Drops below trigger
    executed_sl_ids = paper_broker.process_pending_orders(market_update_feed_sl)
    print(f"Executed SL order IDs: {executed_sl_ids}")
    print("Orderbook after SL processing:", paper_broker.get_orders(sl_order_id))
    print("Positions after SL SELL:", paper_broker.get_positions(market_data_feed=market_update_feed_sl)) # Should be flat or 0 for ANOTHER.NS
    print("Account State:", json.dumps(paper_broker.get_account_balance(), indent=2))


    paper_broker.disconnect()
    print("\nPaperBroker tests completed.")
