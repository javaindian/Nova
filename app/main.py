import streamlit as st
from datetime import datetime, timedelta

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# --- Project Imports ---
# Check if these paths are correct relative to where streamlit run app/main.py is executed
# Assuming execution from project root:
try:
    from database.db_manager import DBManager
    from strategies.nova_strategy import NovaStrategy
    from data_fetchers.yfinance_fetcher import YFinanceFetcher
    from app.brokers.paper_broker import PaperBroker # Import PaperBroker
    # from app.brokers.fyers_broker import FyersBroker # When ready
except ImportError: # Fallback for direct execution within app directory (less ideal)
    print("Warning: Using fallback imports for app/main.py. Run from project root for consistency.")
    from app.database.db_manager import DBManager
    from app.strategies.nova_strategy import NovaStrategy
    from app.data_fetchers.yfinance_fetcher import YFinanceFetcher
    from app.brokers.paper_broker import PaperBroker


# --- Page Configuration ---
st.set_page_config(
    page_title="Nova Trading Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions / Charting Utilities ---
def create_trading_chart(df_plot, signals_on_chart=None, instrument_symbol=""):
    """
    Creates an interactive Plotly chart with Heikin Ashi candles, Nova bands, and signals.
    df_plot should be the output from NovaStrategy.get_plotting_data()
    """
    if df_plot is None or df_plot.empty:
        fig = go.Figure()
        fig.update_layout(title_text=f"No data available for {instrument_symbol}", xaxis_rangeslider_visible=False)
        return fig

    fig = go.Figure()

    # 1. Heikin Ashi Candles (already named 'open', 'high', 'low', 'close' in df_plot)
    candle_colors_up = '#06B690'
    candle_colors_dn = '#B67006'

    fig.add_trace(go.Candlestick(x=df_plot.index,
                                 open=df_plot['open'],
                                 high=df_plot['high'],
                                 low=df_plot['low'],
                                 close=df_plot['close'],
                                 name="Heikin Ashi"))

    # 2. Nova Bands (sma_high_band, sma_low_band)
    band_color = 'rgba(128, 128, 128, 0.3)'
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['sma_high_band'], mode='lines',
                             line=dict(color=band_color, width=1), name='SMA High Band'))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['sma_low_band'], mode='lines',
                             line=dict(color=band_color, width=1), name='SMA Low Band',
                             fill='tonexty', fillcolor='rgba(128, 128, 128, 0.1)'))

    # 3. Plot Buy/Sell Signals
    if signals_on_chart:
        buy_signals = [s for s in signals_on_chart if s['signal_type'] == 'BUY']
        sell_signals = [s for s in signals_on_chart if s['signal_type'] == 'SELL']

        if buy_signals:
            fig.add_trace(go.Scatter(
                x=[s['timestamp'] for s in buy_signals],
                y=[s.get('entry_price', df_plot.loc[s['timestamp']]['low'] if s['timestamp'] in df_plot.index else 0) * 0.99 for s in buy_signals],
                mode='markers', name='Buy Signal',
                marker=dict(symbol='triangle-up', color=candle_colors_up, size=10, line=dict(width=1, color='DarkSlateGrey'))
            ))
        if sell_signals:
            fig.add_trace(go.Scatter(
                x=[s['timestamp'] for s in sell_signals],
                y=[s.get('entry_price', df_plot.loc[s['timestamp']]['high'] if s['timestamp'] in df_plot.index else 0) * 1.01 for s in sell_signals],
                mode='markers', name='Sell Signal',
                marker=dict(symbol='triangle-down', color=candle_colors_dn, size=10, line=dict(width=1, color='DarkSlateGrey'))
            ))

        latest_signal = signals_on_chart[-1] if signals_on_chart else None
        if latest_signal:
            line_style = dict(color="grey", width=1, dash="dash")
            if latest_signal.get('sl_price'):
                fig.add_hline(y=latest_signal['sl_price'], line=line_style, annotation_text="SL", annotation_position="bottom right")
            if latest_signal.get('tp1'):
                fig.add_hline(y=latest_signal['tp1'], line=line_style, annotation_text="TP1", annotation_position="bottom right")

    fig.update_layout(
        title_text=f"{instrument_symbol} - Heikin Ashi & NovaV2 Strategy",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        legend_title_text="Legend"
    )
    return fig


# --- Application State (using Streamlit Session State) ---
if 'db_manager' not in st.session_state:
    try:
        st.session_state.db_manager = DBManager()
        if not st.session_state.db_manager.connection or not st.session_state.db_manager.connection.is_connected():
            st.error("Failed to connect to the database. Please check `app/setup_mysql.py` and your `.env` file.")
            st.stop()
    except Exception as e:
        st.error(f"Error initializing DBManager: {e}. Ensure MySQL is running and configured.")
        st.stop()

if 'data_fetcher_yf' not in st.session_state:
    st.session_state.data_fetcher_yf = YFinanceFetcher()
# if 'fyers_fetcher' not in st.session_state:
# st.session_state.fyers_fetcher = FyersFetcher() # Initialize when ready

if 'nova_strategy' not in st.session_state:
    strategy_params_from_db = st.session_state.db_manager.get_strategy_params('NovaV2')
    if not strategy_params_from_db:
        st.warning("NovaV2 parameters not found in DB, using strategy defaults. Save parameters via sidebar.")
    st.session_state.nova_strategy = NovaStrategy(params=strategy_params_from_db)

if 'paper_broker' not in st.session_state:
    st.session_state.paper_broker = PaperBroker(initial_balance=1000000) # 10 Lakhs
    st.session_state.paper_broker.connect() # Paper broker is always "connected"

# Instrument selection state
if 'instrument_id' not in st.session_state: st.session_state.instrument_id = None
if 'current_instrument_symbol' not in st.session_state: st.session_state.current_instrument_symbol = ""
if 'current_instrument_exchange' not in st.session_state: st.session_state.current_instrument_exchange = ""
if 'current_instrument_asset_type' not in st.session_state: st.session_state.current_instrument_asset_type = ""

# Active Broker State
if 'active_broker_name' not in st.session_state: st.session_state.active_broker_name = "YFinance (Data Only)" # Default to YF
if 'active_broker_instance' not in st.session_state: st.session_state.active_broker_instance = None
if st.session_state.active_broker_name == "Paper Trading (Internal)" and st.session_state.active_broker_instance is None:
    st.session_state.active_broker_instance = st.session_state.paper_broker

# Watchlist filter state
if 'filter_favorites_only' not in st.session_state:
    st.session_state.filter_favorites_only = False

# Telegram Notifier State (initialized once)
if 'telegram_notifier' not in st.session_state:
    # Attempt to load from DB config first, then env vars (handled by TelegramNotifier constructor)
    # For now, TelegramNotifier will try env vars if DB values are not explicitly passed from a settings load.
    # We'll add DB loading for token/chat_id in the settings tab.
    from app.notifications.telegram_bot import TelegramNotifier
    # Initialize without specific token/chat_id; it will try to use env vars or be configured via UI
    st.session_state.telegram_notifier = TelegramNotifier()

# Alert Log State
if 'alert_log' not in st.session_state:
    st.session_state.alert_log = [] # List to store alert messages (timestamp, type, message)

# --- Global Instances (from session state for easy access) ---
db_manager = st.session_state.db_manager
data_fetcher_yf = st.session_state.data_fetcher_yf
nova_strategy = st.session_state.nova_strategy
paper_broker = st.session_state.paper_broker
telegram_notifier = st.session_state.telegram_notifier
# fyers_broker = st.session_state.fyers_broker # When ready

# --- Alerting Function ---
def add_alert(alert_type: str, message: str, send_telegram=True):
    """Adds an alert to the log and optionally sends it via Telegram."""
    timestamp = datetime.now()
    log_entry = {"timestamp": timestamp, "type": alert_type.upper(), "message": message}
    st.session_state.alert_log.insert(0, log_entry) # Add to top
    if len(st.session_state.alert_log) > 100: # Keep only last 100 alerts
        st.session_state.alert_log = st.session_state.alert_log[:100]

    if send_telegram and telegram_notifier.is_configured():
        formatted_telegram_message = f"*{alert_type.upper()}* ({timestamp.strftime('%Y-%m-%d %H:%M:%S')}):\n{message}"
        success, _ = telegram_notifier.send_message(formatted_telegram_message)
        if not success:
            # Add a secondary alert if Telegram failed, but don't try to send THAT via Telegram
            error_log_entry = {"timestamp": datetime.now(), "type": "ERROR", "message": "Failed to send alert via Telegram."}
            st.session_state.alert_log.insert(0, error_log_entry)


# --- Sidebar UI ---
st.sidebar.header("Nova Trading Configuration")

# Instrument Selection
def load_instrument_options():
    instruments_list_all = db_manager.get_all_instruments(favorites_only=st.session_state.filter_favorites_only)
    if not instruments_list_all:
        return {}
    return {f"{i['symbol']} ({i['exchange'] if i['exchange'] else i['asset_type']})": i for i in instruments_list_all}

instrument_options = load_instrument_options()

# Callback to update session state when selectbox changes or favorite filter changes
def instrument_selection_callback():
    # This function is also called by on_change of the filter_favorites_only checkbox
    # Re-load instrument options based on the filter
    # global instrument_options # Make sure we are updating the global one used by selectbox
    # instrument_options = load_instrument_options() # This might not update selectbox options directly if called mid-render
                                                # Instead, rely on Streamlit's rerun to repopulate.

    selected_key = st.session_state.get('selected_instrument_key_selectbox') # Use .get for safety during initial runs

    # Check if the current selected key is still valid in the potentially filtered list
    current_options = load_instrument_options() # Get current valid options
    if selected_key and selected_key in current_options:
        details = current_options[selected_key]
        st.session_state.instrument_id = details['id']
        st.session_state.current_instrument_symbol = details['symbol']
        st.session_state.current_instrument_exchange = details['exchange']
        st.session_state.current_instrument_asset_type = details['asset_type']
    elif current_options: # If current key is invalid but there are other options, select the first one
        first_key = list(current_options.keys())[0]
        st.session_state.selected_instrument_key_selectbox = first_key # Update the selectbox's state
        details = current_options[first_key]
        st.session_state.instrument_id = details['id']
        st.session_state.current_instrument_symbol = details['symbol']
        st.session_state.current_instrument_exchange = details['exchange']
        st.session_state.current_instrument_asset_type = details['asset_type']
    else: # No options available (e.g. no favorites and filter is on)
        st.session_state.instrument_id = None
        st.session_state.current_instrument_symbol = ""
        st.session_state.current_instrument_exchange = ""
        st.session_state.current_instrument_asset_type = ""
        st.session_state.selected_instrument_key_selectbox = None # Clear selectbox selection


# Checkbox for filtering favorites
st.session_state.filter_favorites_only = st.sidebar.checkbox(
    "Show Favorites Only",
    value=st.session_state.filter_favorites_only,
    key="filter_favorites_cb",
    on_change=instrument_selection_callback # Rerun and update options when this changes
)
instrument_options = load_instrument_options() # Reload options based on checkbox state for the selectbox

# Select instrument
selected_instrument_key = st.sidebar.selectbox(
    "Select Instrument",
    options=list(instrument_options.keys()),
    key='selected_instrument_key_selectbox',
    on_change=instrument_selection_callback,
    index=0 if list(instrument_options.keys()) else -1 # Handle empty options
)

# Initial call to set details if not already set (e.g. on first load or after filter change)
if not st.session_state.current_instrument_symbol and instrument_options:
    instrument_selection_callback()


# Timeframe Selection
timeframe_options = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M'] # From schema.sql
primary_tf = st.sidebar.selectbox("Primary Timeframe", timeframe_options, index=3) # Default '15m'
higher_tf = st.sidebar.selectbox("Higher Timeframe", timeframe_options, index=5) # Default '1h'


# Strategy Parameters
st.sidebar.subheader(f"{nova_strategy.strategy_name} Parameters")
# Load current params from strategy object (which got them from DB or its own defaults)
current_ui_params = nova_strategy.params.copy()

# Use a loop for sliders for maintainability if more params are added
param_config = nova_strategy.get_default_params() # Get defaults to know ranges/types conceptually

# Slider for 'length'
current_ui_params['length'] = st.sidebar.slider(
    "Trend Length (length)", min_value=1, max_value=50,
    value=int(current_ui_params.get('length', param_config.get('length'))), # Ensure int for slider
    help=nova_strategy.get_default_params().get('length_description', "EMA length for trend bands")
)
# Slider for 'target_offset'
current_ui_params['target_offset'] = st.sidebar.slider(
    "Target Offset (target_offset)", min_value=0, max_value=10,
    value=int(current_ui_params.get('target_offset', param_config.get('target_offset'))),
    help=nova_strategy.get_default_params().get('target_offset_description', "Adjusts ATR multiples for TP")
)
# Slider for 'atr_period'
current_ui_params['atr_period'] = st.sidebar.slider(
    "ATR Period (atr_period)", min_value=1, max_value=100,
    value=int(current_ui_params.get('atr_period', param_config.get('atr_period'))),
    help=nova_strategy.get_default_params().get('atr_period_description', "Period for ATR calculation")
)
# Slider for 'atr_sma_period'
current_ui_params['atr_sma_period'] = st.sidebar.slider(
    "ATR SMA Period (atr_sma_period)", min_value=1, max_value=100,
    value=int(current_ui_params.get('atr_sma_period', param_config.get('atr_sma_period'))),
    help=nova_strategy.get_default_params().get('atr_sma_period_description', "Period for SMA of ATR")
)
# Slider for 'atr_multiplier'
current_ui_params['atr_multiplier'] = st.sidebar.slider(
    "ATR Multiplier (atr_multiplier)", min_value=0.1, max_value=3.0,
    value=float(current_ui_params.get('atr_multiplier', param_config.get('atr_multiplier'))), # Ensure float
    step=0.1,
    help=nova_strategy.get_default_params().get('atr_multiplier_description', "Multiplier for ATR in band calculation")
)
# Slider for 'mtfa_ema_length'
current_ui_params['mtfa_ema_length'] = st.sidebar.slider(
    "MTFA EMA Length (mtfa_ema_length)", min_value=5, max_value=200,
    value=int(current_ui_params.get('mtfa_ema_length', param_config.get('mtfa_ema_length'))),
    help=nova_strategy.get_default_params().get('mtfa_ema_length_description', "EMA length for higher timeframe trend confirmation")
)


if st.sidebar.button("Apply & Save Parameters"):
    try:
        # Include MTFA EMA length in parameters passed to strategy
        # current_ui_params is already being updated by the sliders directly
        nova_strategy.set_params(current_ui_params) # This also validates

        params_to_save_db = {}
        for k, v in current_ui_params.items():
            param_type = 'JSON' if isinstance(v, list) else \
                         'FLOAT' if isinstance(v, float) else \
                         'INT' if isinstance(v, int) else \
                         'BOOLEAN' if isinstance(v, bool) else 'STRING'
            # Ensure all keys from current_ui_params are added to params_to_save_db
            params_to_save_db[k] = {'value': v, 'type': param_type, 'description': f'{k} for NovaV2'}

        db_manager.save_strategy_params(nova_strategy.strategy_name, params_to_save_db)
        st.sidebar.success(f"{nova_strategy.strategy_name} parameters applied and saved to DB!")
        st.experimental_rerun()
    except ValueError as e:
        st.sidebar.error(f"Error in parameters: {e}")
        add_alert("ERROR", f"Parameter validation error: {e}", send_telegram=False)


# Broker Connection & Controls
st.sidebar.subheader("Broker Settings")
broker_options = ["Paper Trading (Internal)", "Fyers (Live/Paper - TBD)", "YFinance (Data Only)"]
# Determine default index for broker_platform selectbox
default_broker_idx = 0
if st.session_state.active_broker_name in broker_options:
    default_broker_idx = broker_options.index(st.session_state.active_broker_name)

selected_broker_name = st.sidebar.selectbox(
    "Select Trading Mode/Broker",
    broker_options,
    index=default_broker_idx,
    key="broker_platform_selectbox"
)

# Update active broker instance based on selection
if selected_broker_name != st.session_state.active_broker_name: # If selection changed
    st.session_state.active_broker_name = selected_broker_name
    if selected_broker_name == "Paper Trading (Internal)":
        st.session_state.active_broker_instance = paper_broker
        if not paper_broker.is_connected: paper_broker.connect() # Should always be true for paper
        st.sidebar.success("Switched to Paper Trading Mode.")
    elif selected_broker_name == "Fyers (Live/Paper - TBD)":
        # st.session_state.active_broker_instance = fyers_broker # When fyers_broker is ready
        st.session_state.active_broker_instance = None # For now
        st.sidebar.warning("Fyers Broker integration is TBD.")
    else: # YFinance (Data Only)
        st.session_state.active_broker_instance = None
        st.sidebar.info("Switched to Data Only mode (YFinance).")
    st.experimental_rerun()


if st.session_state.active_broker_name == "Fyers (Live/Paper - TBD)":
    fyers_api_key = st.sidebar.text_input("Fyers API Key", type="password", key="fyers_api_key_input")
    fyers_api_secret = st.sidebar.text_input("Fyers API Secret", type="password", key="fyers_api_secret_input")
    # Add other Fyers specific inputs like client_id, totp_key, pin if needed for connection
    if st.sidebar.button("Connect Fyers"):
        st.sidebar.info(f"Fyers connection attempt - TBD.")
        # Here you would call: fyers_broker.connect(api_key=fyers_api_key, ...)
        # And update st.session_state.active_broker_instance = fyers_broker if successful

# Display current paper broker balance if active
if st.session_state.active_broker_name == "Paper Trading (Internal)" and paper_broker:
    paper_balance = paper_broker.get_account_balance()
    st.sidebar.metric("Paper Account Value", f"₹{paper_balance.get('portfolio_value', 0):,.2f}")
    if st.sidebar.button("Reset Paper Account"):
        paper_broker.reset_account()
        st.sidebar.success("Paper account reset to initial balance.")
        st.experimental_rerun()

# Main Area Tabs
tab_titles = ["📊 Chart", "📈 Signals Log", "💼 Paper Trading", "⚙️ Backtest", "📋 Logs", "🗄️ DB Management"]
if st.session_state.active_broker_name == "Fyers (Live/Paper - TBD)":
    tab_titles[2] = " 거래 Fyers Trading" # Change tab name for Fyers
tabs = st.tabs(tab_titles)

tab_chart = tabs[0]
tab_signals = tabs[1]
tab_trading_live_paper = tabs[2] # This tab's content will depend on selected broker
tab_backtest = tabs[3]
tab_logs = tabs[4]
tab_db_manage = tabs[5]


with tab_chart:
    st.header(f"Interactive Chart: {st.session_state.current_instrument_symbol or 'No Instrument Selected'} - {primary_tf}")

    col1_date, col2_date, col3_action = st.columns([2,2,1])
    with col1_date:
        start_date_chart = st.date_input("Start Date", datetime.now().date() - timedelta(days=90), key="chart_start_date")
    with col2_date:
        end_date_chart = st.date_input("End Date", datetime.now().date(), key="chart_end_date")
    with col3_action:
        st.write("")
        st.write("")
        refresh_chart_btn = st.button("Load Chart Data", key="refresh_chart")

    chart_placeholder = st.empty()
    signals_on_chart_details = st.empty()

    if refresh_chart_btn and st.session_state.current_instrument_symbol and primary_tf and start_date_chart and end_date_chart:
        if start_date_chart >= end_date_chart:
            chart_placeholder.warning("Start date must be before end date.")
        else:
            data_source = data_fetcher_yf # Default to YF
            # if st.session_state.active_broker_name == "Fyers (Live/Paper - TBD)" and fyers_broker and fyers_broker.is_connected:
            # data_source = fyers_broker # Or fyers_data_fetcher if separate

            with st.spinner(f"Fetching OHLC data for {st.session_state.current_instrument_symbol} via {st.session_state.active_broker_name}..."):
                ohlc_data = data_source.get_historical_data( # Use selected data_source
                    st.session_state.current_instrument_symbol, # Needs mapping for Fyers (e.g. NSE:RELIANCE-EQ)
                    primary_tf,
                    start_date_chart,
                    end_date_chart
                )

            if ohlc_data is not None and not ohlc_data.empty:
                with st.spinner("Generating strategy plot data and signals..."):
                    df_plot_data = nova_strategy.get_plotting_data(ohlc_data.copy())
                    signals_for_plot = nova_strategy.generate_signals(ohlc_data.copy())

                if df_plot_data is not None and not df_plot_data.empty:
                    fig = create_trading_chart(df_plot_data, signals_for_plot, st.session_state.current_instrument_symbol)
                    chart_placeholder.plotly_chart(fig, use_container_width=True)

                    if signals_for_plot:
                        signals_on_chart_details.subheader("Signals on Chart (Strategy Output):")
                        for sig in signals_for_plot[-5:]:
                            sig_display = (f"- {sig['timestamp']:%Y-%m-%d %H:%M} {sig['signal_type']} @ {sig.get('entry_price', 0):.2f} "
                                           f"(SL: {sig.get('sl_price', 0):.2f}, TP1: {sig.get('tp1', 0):.2f})")
                            signals_on_chart_details.markdown(sig_display)

                            # Add button to Paper Trade this signal
                            if st.session_state.active_broker_name == "Paper Trading (Internal)" and paper_broker:
                                if signals_on_chart_details.button(f"Paper Trade {sig['signal_type']} for {st.session_state.current_instrument_symbol}", key=f"papertrade_{sig['timestamp']}_{sig['signal_type']}"):
                                    # Simulate with last known close from ohlc_data as current_ltp
                                    last_ohlc_candle = ohlc_data.iloc[-1] if not ohlc_data.empty else None
                                    current_ltp_for_trade = last_ohlc_candle['close'] if last_ohlc_candle is not None else sig.get('entry_price')

                                    trade_resp = paper_broker.place_order(
                                        symbol=st.session_state.current_instrument_symbol, # Paper broker can use generic symbol
                                        transaction_type=sig['signal_type'],
                                        quantity=1, # TODO: Implement quantity logic
                                        order_type="MARKET", # Simulate market order for paper trade based on signal
                                        current_ltp=current_ltp_for_trade,
                                        # Pass SL/TP for potential bracket order simulation later
                                        # sl_price=sig.get('sl_price'), tp_price=sig.get('tp1')
                                    )
                                    if trade_resp.get('status') == 'success':
                                        signals_on_chart_details.success(f"Paper trade placed: {trade_resp.get('message')}")
                                        # Optionally save this paper trade execution to DB if a table exists for it
                                        add_alert("PAPER TRADE", f"Placed for {st.session_state.current_instrument_symbol}: {sig['signal_type']} @ {trade_resp.get('filled_price', 'N/A')}. Order ID: {trade_resp.get('order_id')}")
                                    else:
                                        signals_on_chart_details.error(f"Paper trade failed: {trade_resp.get('message')}")
                                        add_alert("ERROR", f"Paper trade failed for {st.session_state.current_instrument_symbol}: {trade_resp.get('message')}")
                    else:
                        signals_on_chart_details.info("No signals generated by the strategy for this period.")
                else:
                    chart_placeholder.warning("Could not generate plot data from OHLC.")
                    add_alert("WARNING", f"Could not generate plot data from OHLC for {st.session_state.current_instrument_symbol}.", send_telegram=False)
            else:
                chart_placeholder.warning(f"No OHLC data found for {st.session_state.current_instrument_symbol} in the selected range/timeframe.")
    elif refresh_chart_btn:
        chart_placeholder.error("Please select an instrument and ensure date range is valid.")


with tab_signals: # Historical Signals Log from DB
    st.header("Historical Signals Log (from Database)")
    # ... (rest of tab_signals code remains largely the same, ensure db_manager is used from session_state if needed) ...
    st.write(f"Displaying signals for: {st.session_state.current_instrument_symbol or 'All Instruments'}")

    col_sig1, col_sig2, col_sig3 = st.columns(3)
    sig_limit = col_sig1.number_input("Number of signals to show", min_value=5, max_value=500, value=50, step=5, key="siglog_limit")
    sig_status_filter = col_sig2.multiselect("Filter by Status",
                                             options=['NEW','ACTIVE','TRIGGERED','CANCELLED','SL_HIT','TP_HIT','EXPIRED'],
                                             default=['NEW', 'ACTIVE'], key="siglog_status")

    refresh_signals_btn_log = col_sig3.button("Refresh Signals Table", key="refresh_signals_log_btn")

    if refresh_signals_btn_log or 'historical_signals_df' not in st.session_state:
        historical_signals_db = db_manager.get_signals(
            instrument_id=st.session_state.instrument_id,
            status=sig_status_filter if sig_status_filter else None,
            limit=sig_limit
        )
        if historical_signals_db:
            st.session_state.historical_signals_df = pd.DataFrame(historical_signals_db)
        else:
            st.session_state.historical_signals_df = pd.DataFrame()

    if 'historical_signals_df' in st.session_state and not st.session_state.historical_signals_df.empty:
        signals_df_display = st.session_state.historical_signals_df.copy()
        display_cols = ['id', 'symbol', 'timestamp', 'signal_type', 'entry_price', 'sl_price', 'tp1', 'status', 'strategy_version', 'details']
        signals_df_display = signals_df_display[[col for col in display_cols if col in signals_df_display.columns]]
        st.dataframe(signals_df_display, use_container_width=True, height=400)

        csv_export = signals_df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Signals as CSV", data=csv_export,
            file_name=f"signals_{st.session_state.current_instrument_symbol or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime='text/csv', key="siglog_csv_btn"
        )
    elif refresh_signals_btn_log:
        st.info("No historical signals found in the database matching the current filters.")


with tab_trading_live_paper:
    st.header(f"{st.session_state.active_broker_name} - Trading Terminal")

    if st.session_state.active_broker_name == "Paper Trading (Internal)" and paper_broker:
        st.subheader("Paper Account Status")
        paper_bal = paper_broker.get_account_balance()
        col_pb1, col_pb2, col_pb3 = st.columns(3)
        col_pb1.metric("Cash", f"₹{paper_bal.get('total_cash',0):,.2f}")
        col_pb2.metric("Portfolio Value", f"₹{paper_bal.get('portfolio_value',0):,.2f}")
        col_pb3.metric("Unrealized PnL", f"₹{paper_bal.get('unrealized_pnl',0):,.2f}")

        st.subheader("Paper Positions")
        paper_positions = paper_broker.get_positions(market_data_feed=None) # Pass live feed if available
        if paper_positions:
            st.dataframe(pd.DataFrame(paper_positions), use_container_width=True)
        else:
            st.info("No open paper positions.")

        st.subheader("Paper Orders")
        paper_orders = paper_broker.get_orders()
        if paper_orders:
            st.dataframe(pd.DataFrame(paper_orders), use_container_width=True)
        else:
            st.info("No paper orders found.")

        # TODO: Add manual paper trade entry form if needed

    elif st.session_state.active_broker_name == "Fyers (Live/Paper - TBD)":
        st.info("Fyers live/paper trading terminal integration is pending.")
        # Here you would display Fyers account details, positions, orders using fyers_broker instance
    else: # YFinance (Data Only)
        st.info("Trading terminal not applicable for 'YFinance (Data Only)' mode.")


with tab_backtest: # Backtest Tab
    st.header("Strategy Backtesting Engine (TBD)")
    st.info("This section will allow running the NovaV2 strategy (and others) over historical data with selected parameters and view detailed performance reports.")

    # Configuration options for backtesting (example placeholders):
    bt_instrument = st.selectbox("Backtest Instrument", options=list(instrument_options.keys()), key="bt_instrument")
    bt_primary_tf = st.selectbox("Backtest Primary TF", timeframe_options, index=3, key="bt_tf")
    col_bt_date1, col_bt_date2 = st.columns(2)
    bt_start_date = col_bt_date1.date_input("Backtest Start Date", datetime.now().date() - timedelta(days=365), key="bt_start")
    bt_end_date = col_bt_date2.date_input("Backtest End Date", datetime.now().date(), key="bt_end")

    # Use current sidebar params for backtest or allow override
    st.subheader("Parameters for Backtest (uses current sidebar settings)")
    st.json(nova_strategy.params) # Display current strategy params

    if st.button("Run Backtest (Conceptual)"):
        st.write(f"Conceptual backtest initiated for {bt_instrument} from {bt_start_date} to {bt_end_date} on {bt_primary_tf}...")
        # In a real backtester:
        # 1. Fetch historical data for the period.
        # 2. Instantiate strategy with current_ui_params.
        # 3. Iterate through data, generate signals, simulate trades.
        # 4. Calculate performance metrics.
        # 5. Store/display results.
        with st.spinner("Simulating backtest..."):
            import time; time.sleep(2) # Simulate work
            st.subheader("Conceptual Backtest Results for NovaV2")
            st.metric("Total Trades", "125")
            st.metric("Win Rate", "62%")
            st.metric("Net Profit", "$ 2,580.75 (Conceptual)")
            st.metric("Sharpe Ratio", "1.25 (Conceptual)")
            st.text_area("Detailed Log (Conceptual)", "Trade 1: BUY ... Profit $50\nTrade 2: SELL ... Loss -$25\n...")

with tab_logs:
    st.header("Application & Trading Logs (TBD)")
    # In a real app, this would tail a log file or query a logging database.
    log_messages = [
        f"{datetime.now()}: Application started.",
        f"{datetime.now() - timedelta(seconds=10)}: UI initialized. Selected: {st.session_state.current_instrument_symbol or 'None'}.",
        f"{datetime.now() - timedelta(seconds=5)}: Chart data refreshed for {st.session_state.current_instrument_symbol or 'None'}.",
        "No new live signals generated in last check (conceptual)."
    ]
    st.text_area("Current Logs (Conceptual)", "\n".join(log_messages), height=300)
    if st.button("Refresh App Logs"):
        st.experimental_rerun()

with tab_db_manage:
    st.header("Database Management Utilities")
    st.info("Use with caution. Ensure you have backups if needed.")

    # --- Watchlist Management Section ---
    st.subheader("Manage Watchlist (Favorite Instruments)")

    # Fetch all instruments for the management table
    all_instruments_for_watchlist = db_manager.get_all_instruments(favorites_only=False)
    if all_instruments_for_watchlist:
        df_instruments = pd.DataFrame(all_instruments_for_watchlist)

        # Create a dictionary to hold the state of checkboxes
        # Initialize from the 'is_favorite' status in the DataFrame
        if 'instrument_fav_states' not in st.session_state:
            st.session_state.instrument_fav_states = {row['id']: row['is_favorite'] for index, row in df_instruments.iterrows()}

        # Ensure all current instruments are in the fav_states (e.g. if new ones added via setup_mysql)
        for index, row in df_instruments.iterrows():
            if row['id'] not in st.session_state.instrument_fav_states:
                 st.session_state.instrument_fav_states[row['id']] = row['is_favorite']


        edited_data = []
        cols_watchlist = st.columns([3, 2, 1, 2]) # Symbol, Exchange, Asset Type, Favorite Toggle
        cols_watchlist[0].markdown("**Symbol**")
        cols_watchlist[1].markdown("**Exchange**")
        cols_watchlist[2].markdown("**Asset Type**")
        cols_watchlist[3].markdown("**Is Favorite?**")

        for index, row in df_instruments.iterrows():
            cols = st.columns([3, 2, 1, 2])
            cols[0].text(row['symbol'])
            cols[1].text(row['exchange'])
            cols[2].text(row['asset_type'])

            # Use the session state for the checkbox value
            is_fav = cols[3].checkbox("", value=st.session_state.instrument_fav_states.get(row['id'], False), key=f"fav_{row['id']}")

            # If checkbox state changed, update session state and DB
            if is_fav != st.session_state.instrument_fav_states.get(row['id']):
                st.session_state.instrument_fav_states[row['id']] = is_fav
                db_manager.set_instrument_favorite_status(row['id'], is_fav)
                st.success(f"{row['symbol']} favorite status updated to {is_fav}. Reloading instrument list...")
                st.experimental_rerun() # Rerun to update sidebar options

    else:
        st.write("No instruments found in the database to manage watchlist.")

    st.markdown("---") # Separator

    # Add New Instrument Form (simplified)
    st.subheader("Add New Instrument to Database")
    with st.form("add_instrument_form"):
        new_symbol = st.text_input("Symbol (e.g., RELIANCE.NS, BTC-USD, NSE:NIFTYBEES-BE)")
        new_name = st.text_input("Name (e.g., Reliance Industries Ltd.)")
        new_exchange = st.text_input("Exchange (e.g., NSE, CRYPTO_EXCHANGE, BSE)")
        new_asset_type = st.selectbox("Asset Type", ["EQUITY", "INDEX", "CRYPTO", "FOREX", "COMMODITY", "ETF"], index=0)
        new_is_favorite = st.checkbox("Add to Favorites?", value=True)
        submitted_add = st.form_submit_button("Add Instrument")

        if submitted_add:
            if new_symbol and new_exchange: # Basic validation
                # Check if exchange is part of symbol e.g. NSE:RELIANCE
                if ':' in new_symbol and not new_exchange: # If exchange is in symbol, parse it
                    parts = new_symbol.split(':',1)
                    parsed_exchange = parts[0].upper()
                    parsed_symbol = parts[1]
                    # Potentially update new_exchange and new_symbol here if logic demands
                    # For now, assume user input is what's intended or db_manager handles it.

                result_id = db_manager.add_instrument(
                    symbol=new_symbol.upper(),
                    name=new_name,
                    exchange=new_exchange.upper(),
                    asset_type=new_asset_type.upper(),
                    is_favorite=new_is_favorite
                )
                if result_id: # Assuming add_instrument returns lastrowid or similar on success
                    st.success(f"Instrument '{new_symbol}' added/updated successfully with ID: {result_id}!")
                    st.session_state.instrument_fav_states.clear() # Clear to force reload on next interaction
                    st.experimental_rerun() # Reload to update lists
                else:
                    st.error(f"Failed to add/update instrument '{new_symbol}'. Check for duplicates or DB errors.")
            else:
                st.error("Symbol and Exchange are required to add an instrument.")

    st.markdown("---")


    st.subheader("Strategy Parameters Table (NovaV2)")
    nova_params_from_db_display = db_manager.get_strategy_params('NovaV2') # Fetches parsed params
    if nova_params_from_db_display:
        st.json(nova_params_from_db_display)
    else:
        st.write("No NovaV2 parameters found in DB. Save them from the sidebar.")

    if st.button("Re-run Initial DB Setup (app/setup_mysql.py)"):
        with st.spinner("Attempting to run initial DB setup script..."):
            try:
                # This is tricky to call directly and see output in Streamlit.
                # For simplicity, we'll just inform the user.
                # import subprocess
                # process = subprocess.run(['python', 'app/setup_mysql.py'], capture_output=True, text=True, check=True)
                # st.text_area("Setup Script Output:", process.stdout + "\n" + process.stderr, height=200)
                st.success("If `app/setup_mysql.py` is runnable and DB connection is valid, it would attempt setup.")
                st.info("Please check your console if running Streamlit locally for output from `setup_mysql.py` if it were executed, or run it manually.")
                st.warning("This button is conceptual for now. Run `python app/setup_mysql.py` from your terminal.")
            except Exception as e:
                st.error(f"Error trying to conceptualize setup script run: {e}")


# --- Main Trading Loop (Conceptual - Streamlit apps are usually event-driven) ---
# A background process or a separate script would typically run the main_trading_loop.
# For a pure Streamlit app, actions are triggered by user interaction or scheduled data refreshes.
# st.sidebar.info("This is a UI for configuration and monitoring. The trading loop would run separately.")

print(f"Streamlit app `main.py` loaded/reloaded at {datetime.now()}. Current Instrument ID: {st.session_state.get('instrument_id')}")
