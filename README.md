# Nova Trading Platform (Nova V2 Strategy)

This application allows users to configure and run the Nova V2 trading strategy, analyze its signals on interactive charts, manage a watchlist of favorite instruments, and receive alerts via a Telegram bot. It supports paper trading and is designed with a modular structure for future expansion.

## Features

*   **Nova V2 Strategy Implementation**: Core trading logic based on the Nova V2 Pine Script.
*   **Interactive Charting**: Heikin Ashi candles with strategy overlays (bands, signals) using Plotly.
*   **Database Backend**: MySQL for storing instruments, market data, strategy parameters, signals, and application configurations.
*   **Data Fetching**: Supports fetching data via Yahoo Finance (`yfinance`). (Fyers API integration is a placeholder).
*   **Paper Trading**: Simulate trades based on strategy signals without real money.
*   **Watchlist Management**: Users can mark instruments as favorites and filter views accordingly.
*   **Alerting System**: In-app alert panel and optional Telegram bot notifications for important events (signals, trades, errors).
*   **Parameter Tuning**: Strategy parameters can be adjusted via the UI and saved.
*   **AI Scanner (Heuristic)**: Scans watchlist instruments for recent NovaV2 signals and provides simple insights (volume, band proximity).

## Installation

1.  **Prerequisites**:
    *   Python 3.10+
    *   MySQL Server (e.g., version 8.0+)
    *   Git (for cloning the repository)

2.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Create a Virtual Environment** (recommended):
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    This will install Streamlit, Pandas, Plotly, MySQL Connector, python-dotenv, yfinance, requests, fyers-apiv3, and pyotp.

5.  **MySQL Database Setup**:
    *   Ensure your MySQL server is running.
    *   Create a database for the application (e.g., `ai_trading_db`). You can do this via a MySQL client:
        ```sql
        CREATE DATABASE ai_trading_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        ```
    *   Create a MySQL user with permissions to access this database (e.g., `tradearj` as used in `db_manager.py` defaults).
        ```sql
        CREATE USER 'your_user'@'localhost' IDENTIFIED BY 'your_password';
        GRANT ALL PRIVILEGES ON ai_trading_db.* TO 'your_user'@'localhost';
        FLUSH PRIVILEGES;
        ```
        Replace `'your_user'` and `'your_password'` accordingly.

6.  **Environment Configuration (`.env` file)**:
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file with your specific configurations:
        *   **Database**:
            *   `DB_HOST`: Hostname of your MySQL server (usually `localhost`).
            *   `DB_USER`: The MySQL username you created.
            *   `DB_PASSWORD`: The password for the MySQL user.
            *   `DB_NAME`: The name of the database you created (e.g., `ai_trading_db`).
        *   **Telegram Bot (Optional)**: If you want Telegram notifications:
            *   `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token obtained from BotFather.
            *   `TELEGRAM_CHAT_ID`: Your personal Telegram Chat ID or the ID of the group/channel where the bot will send messages.
        *   **Fyers API Credentials (Required for Fyers Integration)**:
            *   `FYERS_APP_ID`: Your Fyers API App ID (e.g., `XXXXXXX-100`).
            *   `FYERS_APP_SECRET`: Your Fyers API App Secret.
            *   `FYERS_CLIENT_ID`: Your Fyers Login Client ID (the one you use to log into Fyers).
            *   `FYERS_REDIRECT_URI`: The Redirect URI configured in your Fyers API app (e.g., `http://localhost:3000/auth_callback` or any other valid URI you control).
            *   `FYERS_PAN_OR_DOB`: Your PAN card number or Date of Birth in `YYYY-MM-DD` format (required for Fyers API V3 token generation). **Handle this sensitive information securely.**
            *   `FYERS_TOTP_KEY`: The secret key for your Time-based One-Time Password (TOTP) if you have 2FA enabled with an authenticator app for your Fyers account.
            *   `FYERS_PIN`: Your 4-digit Fyers account PIN.

7.  **Initialize Database Schema and Default Data**:
    *   Run the setup script. This will create the necessary tables and populate some default instruments and strategy parameters.
    *   From the project root directory:
        ```bash
        python app/setup_mysql.py
        ```
    *   Check the console output for any errors during this process.

## Configuration (In-App)

Once the installation is complete and the application is running, further configuration can be done via the UI:

1.  **Strategy Parameters**:
    *   Navigate to the sidebar.
    *   Adjust the NovaV2 strategy parameters (Trend Length, Target Offset, ATR settings) using the sliders.
    *   Click "Apply & Save Parameters" to save them to the database for future sessions.

2.  **Watchlist (Favorite Instruments)**:
    *   Go to the "⚙️ Settings & DB" tab.
    *   Under "Manage Watchlist", you can:
        *   Mark existing instruments as favorites by checking the "Is Favorite?" box next to them. Changes are saved automatically.
        *   Add new instruments to the database using the "Add New Instrument to Database" form.
    *   In the sidebar, you can toggle "Show Favorites Only" to filter the main instrument selection dropdown.

3.  **Telegram Notifications**:
    *   Go to the "⚙️ Settings & DB" tab.
    *   Under "Telegram Notification Settings":
        *   Enter your **Telegram Bot Token** and **Telegram Chat ID**.
        *   Click "Save & Test Telegram Settings". This will save the credentials to the database (in the `app_config` table) and send a test message to your Telegram chat to confirm the setup.
    *   Alerts for events like new signals (from AI Scanner), paper trades, and critical errors will be sent to this Telegram chat if configured.

4.  **Broker Settings**:
    *   The sidebar allows selecting a "Trading Mode/Broker".
    *   **"Paper Trading (Internal)"**: This is the default simulated trading mode. You can reset the paper trading account from the sidebar.
    *   **"YFinance (Data Only)"**: Uses Yahoo Finance for data; no trading capabilities.
    *   **"Fyers (Live/Paper - TBD)"**:
        *   Allows connecting to your Fyers account for live data and (eventually) trading.
        *   **Connection Process**:
            1.  Enter your Fyers App ID and Redirect URI in the sidebar.
            2.  Click "1. Get Fyers Authorization Link".
            3.  Open the generated link in your browser, log in to Fyers, and authorize the application.
            4.  Copy the `auth_code` from the URL you are redirected to.
            5.  Paste the `auth_code` back into the Streamlit app sidebar.
            6.  Enter your Fyers Client ID (login ID), PIN, current TOTP (from your authenticator app, if 2FA is enabled using TOTP), and your PAN/DOB (as configured in `.env` or entered).
            7.  Click "2. Connect to Fyers".
        *   Once connected, the "Trading" tab will display your Fyers account details (profile, funds, positions, orders).
        *   Ensure all required Fyers credentials (especially `FYERS_APP_SECRET` and `FYERS_PAN_OR_DOB`) are correctly set in your `.env` file for the connection to succeed.

## Running the Application

1.  Ensure your virtual environment is activated.
2.  Make sure your MySQL server is running.
3.  From the project root directory, run:
    ```bash
    streamlit run app/main.py
    ```
4.  Open the URL provided by Streamlit (usually `http://localhost:8501`) in your web browser.

## Usage Overview

*   **Sidebar**: Configure instrument, timeframes, strategy parameters, and broker mode.
*   **📊 Chart Tab**: View interactive Heikin Ashi charts with NovaV2 strategy overlays. Paper trade signals directly from the chart.
*   **📈 Signals Log Tab**: Review historical signals generated by the strategy (loaded from the database).
*   **💼 Trading Tab**: View paper trading account status, positions, and orders. (Will show live data if a live broker is integrated and active).
*   **💡 AI Scanner Tab**: Scan your watchlist for recent NovaV2 signals with heuristic insights.
*   **⚙️ Backtest Tab**: Placeholder for future backtesting engine.
*   **🔔 Alerts Tab**: View a log of recent application alerts (signals, trades, errors).
*   **⚙️ Settings & DB Tab**: Manage your instrument watchlist, add new instruments, and configure Telegram notifications.

## Future Development (Potential AI Enhancements)

*   **Advanced AI Signal Confidence**: Train ML models to predict the success probability of generated signals.
*   **Strategy Parameter Optimization**: Use techniques like genetic algorithms to find optimal strategy parameters for different instruments.
*   **Live Broker Integration**: Fully implement Fyers API for live data and trading.
*   **Automated Trading Loop**: A background process to continuously monitor for signals and execute trades based on user configuration.
