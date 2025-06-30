import mysql.connector
from mysql.connector import Error
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DBManager:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.user = os.getenv('DB_USER', 'tradearj')
        self.password = os.getenv('DB_PASSWORD', '1234') # Replace with your actual password or get from env
        self.database = os.getenv('DB_NAME', 'ai_trading_db')
        self.connection = None
        self.connect()

    def connect(self):
        """Establish a database connection."""
        if self.connection is None or not self.connection.is_connected():
            try:
                self.connection = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password
                    # database=self.database # Database will be created if not exists
                )
                if self.connection.is_connected():
                    print(f"Successfully connected to MySQL server: {self.host}")
                    self._create_database_if_not_exists()
                    # Now connect to the specific database
                    self.connection.database = self.database
                    print(f"Switched to database: {self.database}")
            except Error as e:
                print(f"Error connecting to MySQL: {e}")
                self.connection = None # Ensure connection is None if connection failed

    def _create_database_if_not_exists(self):
        """Creates the database if it doesn't exist."""
        if not self.connection or not self.connection.is_connected():
            print("Cannot create database, no connection to server.")
            return
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database '{self.database}' checked/created successfully.")
            cursor.close()
        except Error as e:
            print(f"Error creating database '{self.database}': {e}")


    def close(self):
        """Close the database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed.")

    def execute_query(self, query, params=None, multi=False):
        """Execute a single SQL query."""
        if self.connection is None or not self.connection.is_connected():
            print("No database connection.")
            # Attempt to reconnect
            self.connect()
            if self.connection is None or not self.connection.is_connected():
                return None # Or raise an exception

        cursor = None
        try:
            cursor = self.connection.cursor(dictionary=True if "SELECT" in query.upper() else False)
            if multi:
                # For executing multiple statements from a file or string
                results = []
                for result in cursor.execute(query, params, multi=True):
                     # For operations like CREATE TABLE, result might not be a typical rowset
                    if result.with_rows:
                        results.append(result.fetchall())
                    else:
                        results.append(result.rowcount) # e.g. for INSERT, UPDATE, DELETE
                self.connection.commit()
                return results
            else:
                cursor.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    result = cursor.fetchall()
                    return result
                else:
                    self.connection.commit()
                    return cursor.lastrowid if query.strip().upper().startswith("INSERT") else cursor.rowcount
        except Error as e:
            print(f"Error executing query: {e}\nQuery: {query}\nParams: {params}")
            if self.connection and self.connection.is_connected(): # Check if connection exists before rollback
                try:
                    self.connection.rollback() # Rollback on error
                except Error as rb_error:
                    print(f"Error during rollback: {rb_error}")
            return None
        finally:
            if cursor:
                cursor.close()

    def execute_script(self, sql_script_path):
        """Execute a SQL script from a file."""
        try:
            with open(sql_script_path, 'r', encoding='utf-8') as file:
                sql_script = file.read()

            # Split script into individual statements if mysql.connector does not handle it well directly
            # However, cursor.execute with multi=True should handle most scripts.
            # For very complex scripts or those with delimiters, more robust parsing might be needed.

            # A simple way to split by semicolon, but be cautious with semicolons within strings or comments.
            # sql_commands = [cmd.strip() for cmd in sql_script.split(';') if cmd.strip()]

            print(f"Executing SQL script: {sql_script_path}")
            # Assuming execute_query can handle multi-statement scripts if multi=True passed to cursor.execute
            # The mysql.connector's cursor.execute(operation, multi=True) iterates through results of statements.

            # We need to ensure the connection is to the specific database for table creation
            if self.connection.database != self.database:
                 self.connection.cmd_init_db(self.database)

            return self.execute_query(sql_script, multi=True)
        except FileNotFoundError:
            print(f"Error: SQL script file not found at {sql_script_path}")
            return None
        except Error as e:
            print(f"Error executing SQL script {sql_script_path}: {e}")
            return None

    # --- CRUD Operations for specific tables (examples) ---

    def add_instrument(self, symbol, name=None, exchange=None, asset_type='EQUITY', is_favorite=False):
        """Adds a new instrument to the instruments table."""
        query = """
            INSERT INTO instruments (symbol, name, exchange, asset_type, is_favorite)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name),
                exchange=VALUES(exchange),
                asset_type=VALUES(asset_type),
                is_favorite=VALUES(is_favorite)
        """
        params = (symbol, name, exchange, asset_type, is_favorite)
        return self.execute_query(query, params)

    def get_instrument_id(self, symbol, exchange=None, asset_type='EQUITY'):
        """Retrieves the ID of an instrument by symbol, exchange, and asset_type."""
        query = "SELECT id FROM instruments WHERE symbol = %s"
        params_list = [symbol]
        if exchange: # Note: Fyers symbols might have exchange prefix like NSE:SBIN-EQ
            if ':' in symbol and exchange.upper() in symbol.upper().split(':')[0]: # If exchange info is in symbol
                pass # Symbol might already be specific enough e.g. "NSE:RELIANCE-EQ"
            else:
                query += " AND exchange = %s"
                params_list.append(exchange)

        # Asset type might not always be needed if symbol + exchange is unique enough
        # query += " AND asset_type = %s"
        # params_list.append(asset_type)

        result = self.execute_query(query, tuple(params_list))
        if result:
            return result[0]['id']
        # Fallback if exchange was in symbol e.g. "NSE:RELIANCE"
        if ':' in symbol and not exchange: # Try parsing exchange from symbol
            parts = symbol.split(':', 1)
            parsed_exchange = parts[0]
            parsed_symbol = parts[1]
            query = "SELECT id FROM instruments WHERE symbol = %s AND exchange = %s" # AND asset_type = %s"
            params_list = [parsed_symbol, parsed_exchange] #, asset_type]
            result = self.execute_query(query, tuple(params_list))
            return result[0]['id'] if result else None
        return None


    def get_all_instruments(self, favorites_only=False):
        """Retrieves all instruments from the database, optionally filtered for favorites."""
        query = "SELECT id, symbol, name, exchange, asset_type, is_favorite FROM instruments"
        if favorites_only:
            query += " WHERE is_favorite = TRUE"
        query += " ORDER BY symbol"
        return self.execute_query(query)

    def set_instrument_favorite_status(self, instrument_id, is_favorite: bool):
        """Sets the favorite status for a given instrument ID."""
        query = "UPDATE instruments SET is_favorite = %s WHERE id = %s"
        params = (is_favorite, instrument_id)
        return self.execute_query(query, params)

    def store_market_data(self, instrument_id, timestamp, open_price, high_price, low_price, close_price, volume, timeframe, is_heikin_ashi=False):
        """Stores market data for an instrument."""
        query = """
            INSERT INTO market_data (instrument_id, timestamp, open, high, low, close, volume, timeframe, is_heikin_ashi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close), volume=VALUES(volume)
        """
        params = (instrument_id, timestamp, open_price, high_price, low_price, close_price, volume, timeframe, is_heikin_ashi)
        return self.execute_query(query, params)

    def get_market_data(self, instrument_id, timeframe, start_date=None, end_date=None, limit=None, is_heikin_ashi=False):
        """
        Retrieves market data for a given instrument and timeframe.
        Timestamps are expected in 'YYYY-MM-DD HH:MM:SS' format if provided.
        """
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_data
            WHERE instrument_id = %s AND timeframe = %s AND is_heikin_ashi = %s
        """
        params = [instrument_id, timeframe, is_heikin_ashi]

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)

        query += " ORDER BY timestamp ASC" # Ensure chronological order for time series

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        return self.execute_query(query, tuple(params))

    def save_strategy_params(self, strategy_name, params_dict):
        """Saves or updates strategy parameters.
        params_dict: {'param_name': {'value': 'val', 'type': 'INT', 'description': 'desc'}, ...}
        """
        results = []
        for name, details in params_dict.items():
            query = """
                INSERT INTO strategy_params (strategy_name, param_name, param_value, param_type, description, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE param_value=VALUES(param_value), param_type=VALUES(param_type),
                                        description=VALUES(description), is_active=VALUES(is_active)
            """
            val = details.get('value')
            # Serialize JSON types
            if details.get('type') == 'JSON' and not isinstance(val, str):
                val = json.dumps(val)

            p = (strategy_name, name, str(val), details.get('type', 'STRING'), details.get('description', None), details.get('is_active', True))
            results.append(self.execute_query(query, p))
        return results

    def get_strategy_params(self, strategy_name):
        """Retrieves all active parameters for a given strategy."""
        query = "SELECT param_name, param_value, param_type FROM strategy_params WHERE strategy_name = %s AND is_active = TRUE"
        params_db = self.execute_query(query, (strategy_name,))

        config = {}
        if params_db:
            for row in params_db:
                val = row['param_value']
                ptype = row['param_type']
                if ptype == 'INT':
                    val = int(val)
                elif ptype == 'FLOAT':
                    val = float(val)
                elif ptype == 'BOOLEAN':
                    val = val.lower() in ['true', '1', 'yes']
                elif ptype == 'JSON':
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON for param {row['param_name']}: {val}")
                config[row['param_name']] = val
        return config

    def add_signal(self, instrument_id, timestamp, signal_type, entry_price=None, sl_price=None,
                   tp1=None, tp2=None, tp3=None, atr_value=None, confidence=None,
                   status='NEW', strategy_version='NovaV2_1.0', details=None, strategy_params_id=None):
        """Adds a new trading signal to the signals table."""
        query = """
            INSERT INTO signals (instrument_id, timestamp, signal_type, entry_price, sl_price,
                                 tp1, tp2, tp3, atr_value, confidence, status, strategy_version, details, strategy_params_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        if isinstance(details, dict): # Ensure details are stored as JSON string
            details = json.dumps(details)

        params = (instrument_id, timestamp, signal_type, entry_price, sl_price,
                  tp1, tp2, tp3, atr_value, confidence, status, strategy_version, details, strategy_params_id)
        return self.execute_query(query, params)

    def get_signals(self, instrument_id=None, status=None, start_date=None, end_date=None, limit=None):
        """Retrieves signals, optionally filtered."""
        query = "SELECT s.*, i.symbol FROM signals s JOIN instruments i ON s.instrument_id = i.id WHERE 1=1"
        filters = []
        if instrument_id:
            query += " AND s.instrument_id = %s"
            filters.append(instrument_id)
        if status:
            query += " AND s.status = %s"
            filters.append(status)
        if start_date:
            query += " AND s.timestamp >= %s"
            filters.append(start_date)
        if end_date:
            query += " AND s.timestamp <= %s"
            filters.append(end_date)

        query += " ORDER BY s.timestamp DESC"
        if limit:
            query += " LIMIT %s"
            filters.append(limit)

        return self.execute_query(query, tuple(filters))

    def update_signal_status(self, signal_id, new_status, details_update=None):
        """Updates the status of an existing signal."""
        query = "UPDATE signals SET status = %s"
        params = [new_status]

        if details_update:
            # For JSON fields, this would ideally be a JSON_MERGE_PATCH or similar
            # For now, we might just append to a text field or overwrite if it's simple text.
            # If 'details' is TEXT and you want to append:
            # query += ", details = CONCAT(COALESCE(details, ''), %s)"
            # params.append(details_update_text)
            # If 'details' is JSON and you want to update/add keys:
            # This requires more complex query building or fetching, modifying, and saving.
            # For simplicity, let's assume details_update is a complete replacement if provided as string
            if isinstance(details_update, dict):
                details_update = json.dumps(details_update)
            query += ", details = %s"
            params.append(details_update)

        query += " WHERE id = %s"
        params.append(signal_id)

        return self.execute_query(query, tuple(params))

    # Placeholder for other CRUD operations like broker_executions, app_config etc.

if __name__ == '__main__':
    # Example Usage & Setup
    db_manager = DBManager()

    if db_manager.connection:
        # 1. Execute the schema to create tables
        print("\nExecuting schema.sql...")
        # Construct the absolute path to schema.sql relative to this script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, "schema.sql")
        db_manager.execute_script(schema_path)
        print("Schema execution attempted.")

        # 2. Add a sample instrument
        print("\nAdding sample instrument...")
        instrument_name = "NIFTY 50"
        instrument_symbol = "NIFTY50" # Example, adjust for your broker
        exchange = "NSE_INDEX" # Example
        asset = "INDEX"
        instr_id = db_manager.add_instrument(instrument_symbol, instrument_name, exchange, asset)
        if instr_id:
            print(f"Instrument '{instrument_name}' added/updated with ID: {instr_id} (if new) or Row Count (if updated).")
        retrieved_id = db_manager.get_instrument_id(instrument_symbol, exchange, asset)
        print(f"Retrieved ID for {instrument_symbol}: {retrieved_id}")


        # 3. Add sample strategy parameters for NovaV2
        print("\nAdding NovaV2 default parameters...")
        nova_params = {
            'length': {'value': 6, 'type': 'INT', 'description': 'EMA length for trend calculation'},
            'target_offset': {'value': 0, 'type': 'INT', 'description': 'Offset for target calculation multiples'},
            'atr_period': {'value': 50, 'type': 'INT', 'description': 'Period for ATR calculation'},
            'atr_sma_period': {'value': 50, 'type': 'INT', 'description': 'Period for SMA of ATR'},
            'atr_multiplier': {'value': 0.8, 'type': 'FLOAT', 'description': 'Multiplier for ATR value in bands'},
            'primary_timeframe': {'value': '15m', 'type': 'STRING', 'description': 'Default primary timeframe'},
            'secondary_timeframes': {'value': ['1h', '4h'], 'type': 'JSON', 'description': 'Default secondary timeframes'}
        }
        db_manager.save_strategy_params('NovaV2', nova_params)
        print("NovaV2 parameters saved.")

        # 4. Retrieve strategy parameters
        print("\nRetrieving NovaV2 parameters...")
        retrieved_params = db_manager.get_strategy_params('NovaV2')
        if retrieved_params:
            print("Retrieved Parameters:")
            for k, v in retrieved_params.items():
                print(f"  {k}: {v} (type: {type(v).__name__})")
        else:
            print("No parameters found for NovaV2.")

        # 5. Add sample market data (requires an instrument_id)
        if retrieved_id:
            print("\nAdding sample market data...")
            from datetime import datetime, timedelta
            # Using a fixed timestamp for reproducibility in tests
            # In a real scenario, these would be dynamic
            ts = datetime(2023, 1, 1, 9, 15, 0)
            db_manager.store_market_data(retrieved_id, ts, 18000.0, 18050.0, 17980.0, 18020.0, 100000, '15m')
            db_manager.store_market_data(retrieved_id, ts + timedelta(minutes=15), 18020.0, 18060.0, 18010.0, 18040.0, 120000, '15m')
            print("Sample market data added.")

            # 6. Retrieve market data
            print("\nRetrieving market data...")
            market_data = db_manager.get_market_data(retrieved_id, '15m', limit=5)
            if market_data:
                print(f"Retrieved {len(market_data)} candles for {instrument_symbol} 15m:")
                for row in market_data:
                    print(f"  {row['timestamp']} O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']} V:{row['volume']}")
            else:
                print("No market data found.")

        # 7. Add a sample signal
        if retrieved_id:
            print("\nAdding sample signal...")
            sig_details = {"ema_val": 18010.50, "atr_band_high": 18055.20}
            db_manager.add_signal(retrieved_id, datetime.now(), 'BUY', entry_price=18040.0, sl_price=17990.0,
                                  tp1=18090.0, atr_value=65.5, details=sig_details)
            print("Sample signal added.")

            # 8. Retrieve signals
            print("\nRetrieving signals...")
            signals = db_manager.get_signals(instrument_id=retrieved_id, limit=5)
            if signals:
                print(f"Retrieved {len(signals)} signals:")
                for s in signals:
                    print(f"  ID: {s['id']}, Symbol: {s['symbol']}, Type: {s['signal_type']}, Status: {s['status']}, Entry: {s['entry_price']}, Details: {s['details']}")
                    if s['id'] and s['status'] == 'NEW': # Example update
                        db_manager.update_signal_status(s['id'], 'ACTIVE', details_update=json.dumps({"activation_time": str(datetime.now())}))
                        print(f"  Signal {s['id']} updated to ACTIVE.")
            else:
                print("No signals found.")


        db_manager.close()
    else:
        print("Failed to connect to the database. Please check your credentials and MySQL server.")

# To run this directly for setup:
# Ensure you have a .env file in the same directory with:
# DB_HOST=localhost
# DB_USER=your_mysql_user
# DB_PASSWORD=your_mysql_password
# DB_NAME=ai_trading_db
#
# Or set these environment variables manually.
# Then run: python app/database/db_manager.py
# This will attempt to connect, create the DB if not exists, create tables from schema.sql, and run sample operations.
