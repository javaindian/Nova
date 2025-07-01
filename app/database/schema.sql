-- MySQL Database Schema for AI Trading Application

-- Table for storing information about tradable instruments
CREATE TABLE IF NOT EXISTS instruments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL,          -- e.g., 'RELIANCE', 'BTCUSDT'
    name VARCHAR(100),                    -- e.g., 'Reliance Industries Ltd', 'Bitcoin / Tether'
    exchange VARCHAR(50),                 -- e.g., 'NSE', 'BINANCE'
    asset_type VARCHAR(20) DEFAULT 'EQUITY', -- e.g., 'EQUITY', 'CRYPTO', 'FOREX', 'COMMODITY'
    is_favorite BOOLEAN DEFAULT FALSE,    -- For user's watchlist
    UNIQUE KEY uk_instrument (symbol, exchange, asset_type) -- Ensure unique combination
);

-- Table for storing historical and real-time market data
CREATE TABLE IF NOT EXISTS market_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument_id INT NOT NULL,
    timestamp DATETIME NOT NULL,
    open DECIMAL(18,8) NOT NULL,    -- Increased precision for crypto/forex
    high DECIMAL(18,8) NOT NULL,
    low DECIMAL(18,8) NOT NULL,
    close DECIMAL(18,8) NOT NULL,
    volume BIGINT,                  -- Changed to BIGINT for larger volumes
    timeframe ENUM('1m','3m','5m','15m','30m','1h','2h','4h','1d','1w','1M') NOT NULL, -- Added more timeframes
    is_heikin_ashi BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE, -- Cascade delete if instrument is removed
    UNIQUE KEY uk_market_data (instrument_id, timestamp, timeframe, is_heikin_ashi) -- Prevent duplicate candles
);
-- Index for faster querying of market data
CREATE INDEX idx_market_data_timestamp ON market_data (timestamp);
CREATE INDEX idx_market_data_instrument_timestamp ON market_data (instrument_id, timestamp DESC);


-- Table for storing parameters for different strategies
CREATE TABLE IF NOT EXISTS strategy_params (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL DEFAULT 'NovaV2', -- Name of the strategy
    param_name VARCHAR(50) NOT NULL,    -- e.g., 'length', 'target', 'atr_period', 'atr_sma_period', 'atr_multiplier'
    param_value VARCHAR(255) NOT NULL,  -- Store diverse types as string, parse in app
    param_type ENUM('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'JSON') DEFAULT 'STRING', -- Type hint for parsing
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,     -- To enable/disable certain param sets
    UNIQUE KEY uk_strategy_param (strategy_name, param_name)
);

-- Example entries for NovaV2 default parameters (can be inserted via script)
-- INSERT INTO strategy_params (strategy_name, param_name, param_value, param_type, description) VALUES
-- ('NovaV2', 'length', '6', 'INT', 'EMA length for trend calculation'),
-- ('NovaV2', 'target_offset', '0', 'INT', 'Offset for target calculation multiples'),
-- ('NovaV2', 'atr_period', '50', 'INT', 'Period for ATR calculation'),
-- ('NovaV2', 'atr_sma_period', '50', 'INT', 'Period for SMA of ATR'),
-- ('NovaV2', 'atr_multiplier', '0.8', 'FLOAT', 'Multiplier for ATR value in bands'),
-- ('NovaV2', 'mtfa_ema_length', '20', 'INT', 'EMA length for Multi-Timeframe Analysis confirmation'),
-- ('NovaV2', 'primary_timeframe', '15m', 'STRING', 'Default primary timeframe for the strategy'),
-- ('NovaV2', 'secondary_timeframes', '["1h", "4h"]', 'JSON', 'Default secondary timeframes for confirmation');


-- Table for storing generated trading signals
CREATE TABLE IF NOT EXISTS signals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument_id INT NOT NULL,
    strategy_params_id INT,            -- Optional: Link to a specific parameter set if versioning them
    timestamp DATETIME NOT NULL,        -- Timestamp of the bar where signal was generated
    signal_type ENUM('BUY','SELL','HOLD') NOT NULL, -- Added 'HOLD'
    entry_price DECIMAL(18,8),          -- Calculated entry price
    sl_price DECIMAL(18,8),             -- Calculated stop-loss price
    tp1 DECIMAL(18,8),                  -- Take Profit 1
    tp2 DECIMAL(18,8),                  -- Take Profit 2
    tp3 DECIMAL(18,8),                  -- Take Profit 3
    atr_value DECIMAL(18,8),            -- ATR value at the time of signal
    confidence FLOAT,                   -- Optional: AI predicted confidence (0.0 to 1.0)
    mtfa_confirmed BOOLEAN DEFAULT NULL, -- Indicates if Multi-Timeframe Analysis condition was met
    status ENUM('NEW','ACTIVE','TRIGGERED','CANCELLED','SL_HIT','TP_HIT','EXPIRED') DEFAULT 'NEW',
    strategy_version VARCHAR(20) DEFAULT 'NovaV2_1.0', -- Version of the strategy logic
    details TEXT,                       -- Store additional JSON details like indicator values
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_params_id) REFERENCES strategy_params(id) ON DELETE SET NULL -- Keep signal if params are deleted
);
-- Index for faster querying of signals
CREATE INDEX idx_signals_instrument_timestamp ON signals (instrument_id, timestamp DESC);
CREATE INDEX idx_signals_status ON signals (status);


-- Table for tracking broker order executions related to signals
CREATE TABLE IF NOT EXISTS broker_executions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    signal_id BIGINT,
    broker_order_id VARCHAR(100) UNIQUE, -- Unique ID from the broker
    parent_order_id VARCHAR(100),       -- For multi-leg orders (e.g. SL/TP brackets)
    instrument_id INT NOT NULL,         -- Denormalized for easier queries
    timestamp DATETIME NOT NULL,        -- Timestamp of execution or last update
    order_type ENUM('MARKET','LIMIT','SL','SL-M','BRACKET') NOT NULL,
    transaction_type ENUM('BUY','SELL') NOT NULL,
    filled_price DECIMAL(18,8),
    average_price DECIMAL(18,8),
    quantity DECIMAL(18,4) NOT NULL,    -- Allow fractional quantities for crypto/forex
    trigger_price DECIMAL(18,8),
    status ENUM('PENDING_OPEN','OPEN','PENDING_CANCEL','COMPLETE','CANCELLED','REJECTED','EXPIRED','AMO_RECEIVED') NOT NULL,
    broker_name VARCHAR(50),            -- e.g., 'Fyers', 'YFinancePaper', 'Zerodha'
    broker_response TEXT,               -- Full API response from broker
    tags VARCHAR(255),                  -- e.g., 'Entry', 'SL', 'TP1'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE SET NULL, -- Keep execution record if signal is deleted
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) -- No cascade, keep record if instrument removed
);
-- Index for faster querying of executions
CREATE INDEX idx_broker_executions_signal_id ON broker_executions (signal_id);
CREATE INDEX idx_broker_executions_status ON broker_executions (status);
CREATE INDEX idx_broker_executions_instrument_timestamp ON broker_executions (instrument_id, timestamp DESC);

-- Table for User/API configurations (e.g. Broker API keys)
-- Store encrypted values in production.
CREATE TABLE IF NOT EXISTS app_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE, -- e.g., 'FYERS_API_KEY', 'FYERS_SECRET_KEY', 'GLOBAL_RISK_PERCENT'
    config_value TEXT NOT NULL, -- Store encrypted if sensitive
    description TEXT,
    is_encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Consider a table for backtesting results if you plan to store detailed reports
CREATE TABLE IF NOT EXISTS backtest_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    instrument_id INT NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    parameters JSON, -- Store strategy parameters used for this backtest
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    max_drawdown DECIMAL(10,4),
    profit_loss DECIMAL(18,4),
    sharpe_ratio DECIMAL(10,4),
    report_details_path VARCHAR(255), -- Path to a more detailed report file (HTML/CSV)
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id)
);

-- Notes:
-- 1. `DECIMAL(18,8)` is used for prices to accommodate cryptocurrencies and forex. Adjust if not needed.
-- 2. `ENUM` types are used for fixed sets of values. Ensure your application logic matches these.
-- 3. Timestamps are generally `DATETIME`. `created_at` and `updated_at` use `TIMESTAMP` for auto-updating.
-- 4. Foreign Key constraints help maintain data integrity. `ON DELETE CASCADE` or `ON DELETE SET NULL` behavior defined.
-- 5. Indexes are crucial for performance on tables with many rows, especially `market_data`, `signals`, and `broker_executions`.
-- 6. The `strategy_params` table is designed to be flexible. You can store various parameters for multiple strategies.
-- 7. `app_config` for API keys: these should be encrypted in a real application. Streamlit secrets or environment variables are safer for direct key storage. This table might hold paths to encrypted files or be used differently based on security model.
-- 8. Added `asset_type` to instruments and expanded `timeframe` options.
-- 9. `broker_order_id` in `broker_executions` should be unique if provided by the broker.

COMMIT;
