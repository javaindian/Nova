import os
from database.db_manager import DBManager
from dotenv import load_dotenv

def main():
    """
    Sets up the MySQL database:
    1. Creates the database if it doesn't exist.
    2. Applies the schema from schema.sql to create/update tables.
    3. Optionally, populates with some initial/default data.
    """
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')) # Load .env from root

    print("Starting database setup...")
    db_manager = DBManager()

    if not db_manager.connection or not db_manager.connection.is_connected():
        print("Failed to connect to MySQL server. Please check your DB_HOST, DB_USER, DB_PASSWORD in .env")
        print("Ensure MySQL server is running and accessible.")
        return

    # 1. Create database (handled by DBManager constructor or connect method)
    # The DBManager's connect method already calls _create_database_if_not_exists

    # 2. Apply schema
    print("\nApplying database schema...")
    # Construct the absolute path to schema.sql relative to this script's location
    # This script is in app/, schema.sql is in app/database/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(script_dir, "database", "schema.sql") # Corrected path

    if not os.path.exists(schema_path):
        print(f"ERROR: schema.sql not found at {schema_path}")
        db_manager.close()
        return

    print(f"Executing schema script from: {schema_path}")
    # The db_manager.execute_script itself prints messages
    schema_results = db_manager.execute_script(schema_path)
    if schema_results is not None: # Check if script execution didn't return None (which indicates an error in execute_script)
        print("Schema applied successfully (or tables already existed).")
        # schema_results from multi=True is a list of results per statement.
        # For CREATE TABLE, it's often just an update count or None if no rows affected/returned.
        # We mainly care that no major error occurred.
    else:
        print("Schema application might have failed. Check db_manager logs.")


    # 3. Populate initial/default data (optional)
    print("\nPopulating initial data (if any)...")

    # Add a few common instruments (example)
    print("Adding/Updating common instruments...")
    instruments_to_add = [
        {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries Ltd.', 'exchange': 'NSE', 'asset_type': 'EQUITY', 'is_favorite': True},
        {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services Ltd.', 'exchange': 'NSE', 'asset_type': 'EQUITY', 'is_favorite': False},
        {'symbol': 'INFY.NS', 'name': 'Infosys Ltd.', 'exchange': 'NSE', 'asset_type': 'EQUITY', 'is_favorite': True},
        {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank Ltd.', 'exchange': 'NSE', 'asset_type': 'EQUITY', 'is_favorite': False},
        {'symbol': 'NIFTY 50', 'name': 'NIFTY 50 Index', 'exchange': 'NSE_INDEX', 'asset_type': 'INDEX', 'is_favorite': True},
        {'symbol': 'BANKNIFTY', 'name': 'NIFTY Bank Index', 'exchange': 'NSE_INDEX', 'asset_type': 'INDEX', 'is_favorite': False},
        {'symbol': 'BTC-USD', 'name': 'Bitcoin / US Dollar', 'exchange': 'CRYPTO_EXCHANGE', 'asset_type': 'CRYPTO', 'is_favorite': True},
        {'symbol': 'ETH-USD', 'name': 'Ethereum / US Dollar', 'exchange': 'CRYPTO_EXCHANGE', 'asset_type': 'CRYPTO', 'is_favorite': False},
    ]
    for inst in instruments_to_add:
        db_manager.add_instrument(
            inst['symbol'], inst['name'], inst['exchange'],
            inst['asset_type'], inst.get('is_favorite', False) # Add is_favorite
        )
    print(f"{len(instruments_to_add)} instruments checked/added.")


    # Add default strategy parameters for NovaV2
    print("\nAdding/Updating NovaV2 default parameters...")
    nova_params_data = {
        'length': {'value': 6, 'type': 'INT', 'description': 'EMA length for trend calculation'},
        'target_offset': {'value': 0, 'type': 'INT', 'description': 'Offset for target calculation multiples (PineScript: target)'},
        'atr_period': {'value': 50, 'type': 'INT', 'description': 'Period for ATR calculation (PineScript: ta.atr(50))'},
        'atr_sma_period': {'value': 50, 'type': 'INT', 'description': 'Period for SMA of ATR (PineScript: ta.sma(atr, 50))'},
        'atr_multiplier': {'value': 0.8, 'type': 'FLOAT', 'description': 'Multiplier for ATR value in bands (PineScript: * 0.8)'},
        'primary_timeframe': {'value': '15m', 'type': 'STRING', 'description': 'Default primary timeframe for the strategy'},
        'secondary_timeframes': {'value': ['1h', '4h'], 'type': 'JSON', 'description': 'Default secondary timeframes for confirmation'}
    }
    db_manager.save_strategy_params('NovaV2', nova_params_data)
    print("NovaV2 default parameters saved.")

    # You could add more default data here, e.g., for app_config table

    print("\nDatabase setup process completed.")
    db_manager.close()

if __name__ == "__main__":
    # This allows running the setup script directly
    # Ensure your .env file is in the root directory (one level up from 'app')
    # Example .env content:
    # DB_HOST=localhost
    # DB_USER=your_user
    # DB_PASSWORD=your_password
    # DB_NAME=ai_trading_db
    main()
