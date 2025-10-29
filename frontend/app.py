"""
Streamlit Trading Interface - Main Application

Multi-page trading dashboard with real-time updates.
"""

import streamlit as st
import time
import sys
import os
from pathlib import Path
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables from frontend/.env
frontend_dir = Path(__file__).parent
env_path = frontend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Page config must be first
st.set_page_config(
    page_title="Crypto Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import using relative paths
from services.api_client import get_api_client
from utils.formatters import format_price, format_quantity, color_by_side, calculate_total, format_order_id

# Get backend URL from environment variable or use default
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
BACKEND_PROTOCOL = os.getenv("BACKEND_PROTOCOL", "http")
BACKEND_URL = f"{BACKEND_PROTOCOL}://{BACKEND_HOST}:{BACKEND_PORT}"

# Initialize session state
if "backend_url" not in st.session_state:
    st.session_state.backend_url = BACKEND_URL
if "active_orders" not in st.session_state:
    st.session_state.active_orders = []
if "recent_trades" not in st.session_state:
    st.session_state.recent_trades = []
if "orderbook_data" not in st.session_state:
    st.session_state.orderbook_data = {}
if "connected" not in st.session_state:
    st.session_state.connected = False
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "BTC-USDT"
if "current_page" not in st.session_state:
    st.session_state.current_page = "Trading"

# Get API client
api_client = get_api_client(st.session_state.backend_url)

# Function to refresh order statuses
def refresh_order_statuses():
    """Refresh the status of all active orders by querying the backend."""
    updated_orders = []
    errors = []
    
    for order in st.session_state.active_orders:
        # Skip orders that are already in final state (filled/cancelled)
        current_status = order.get('status', '').lower()
        if current_status in ['filled', 'cancelled']:
            updated_orders.append(order)
            continue
            
        try:
            # Convert order_id to string if it's a UUID object
            order_id_str = str(order['order_id'])
            symbol_str = str(order['symbol'])
            
            # Fetch current status from backend
            status_response = api_client.get_order_status(
                order_id=order_id_str,
                symbol=symbol_str
            )
            
            # Update order with latest status and filled quantity
            order['status'] = status_response.get('status', order['status'])
            order['filled_quantity'] = status_response.get('filled_quantity', order['filled_quantity'])
            order['remaining_quantity'] = status_response.get('remaining_quantity', order['remaining_quantity'])
            updated_orders.append(order)
            
        except Exception as e:
            # If order not found, it might have been filled and removed from the book
            # Check if it was pending - if so, mark as filled
            if current_status == 'pending':
                order['status'] = 'filled'
                order['filled_quantity'] = order.get('quantity', '0')
                order['remaining_quantity'] = '0'
            
            updated_orders.append(order)
    
    st.session_state.active_orders = updated_orders

# Auto-refresh order statuses every 2 seconds if there are active orders
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

current_time = time.time()
if st.session_state.active_orders and (current_time - st.session_state.last_refresh) > 2:
    refresh_order_statuses()
    st.session_state.last_refresh = current_time

# Sidebar
with st.sidebar:
    st.title("📈 Trading Dashboard")
    
    # Connection status
    if api_client.health_check():
        st.success("🟢 Connected")
        st.session_state.connected = True
    else:
        st.error("🔴 Disconnected")
        st.session_state.connected = False
    
    st.divider()
    
    # Navigation
    pages = ["Trading", "Order Book", "Metrics"]
    default_index = 0
    if st.session_state.current_page in pages:
        default_index = pages.index(st.session_state.current_page)
    
    page = st.radio("Navigation", pages, index=default_index, key="nav_radio")
    st.session_state.current_page = page
    
    st.divider()
    
    # Settings
    with st.expander("⚙️ Settings"):
        st.session_state.backend_url = st.text_input("Backend URL", st.session_state.backend_url)
        auto_refresh = st.checkbox("Auto Refresh", value=True)
        refresh_interval = st.slider("Refresh Interval (s)", 1, 10, 3)

# Main content based on page selection
if page == "Trading":
    st.title("💱 Trading Dashboard")
    
    # Order Entry Section
    with st.container():
        st.subheader("Submit Order")
        
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
        
        with col1:
            symbol = st.selectbox("Symbol", ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"])
            st.session_state.selected_symbol = symbol
        
        with col2:
            order_type = st.selectbox("Order Type", ["Market", "Limit", "IOC", "FOK"])
        
        with col3:
            side = st.radio("Side", ["Buy", "Sell"], horizontal=True)
        
        with col4:
            quantity = st.number_input("Quantity", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
        
        with col5:
            if order_type != "Market":
                price = st.number_input("Price", min_value=0.01, value=50000.0, step=100.0, format="%.2f")
            else:
                st.write("")
                st.write("Market Price")
                price = None
        
        # Quick size buttons
        col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)
        if col_q1.button("0.1"):
            quantity = 0.1
        if col_q2.button("0.5"):
            quantity = 0.5
        if col_q3.button("1.0"):
            quantity = 1.0
        if col_q4.button("5.0"):
            quantity = 5.0
        if col_q5.button("10.0"):
            quantity = 10.0
        
        # Submit button
        submit_col1, submit_col2 = st.columns([1, 4])
        with submit_col1:
            if st.button(f"🟢 {side} {symbol}" if side == "Buy" else f"🔴 {side} {symbol}", use_container_width=True, type="primary"):
                try:
                    # Validate
                    if quantity <= 0:
                        st.error("❌ Quantity must be positive")
                    elif order_type != "Market" and price and price <= 0:
                        st.error("❌ Price must be positive")
                    else:
                        # Submit order
                        with st.spinner("Submitting order..."):
                            result = api_client.submit_order(
                                symbol=symbol,
                                order_type=order_type.lower(),
                                side=side.lower(),
                                quantity=str(quantity),
                                price=str(price) if price else None
                            )
                        
                        st.success(f"✅ Order submitted! ID: {format_order_id(result['order_id'])}")
                        
                        # Show result details
                        with st.expander("Order Details"):
                            st.json(result)
                        
                        # Add to active orders (combine submission data with response)
                        order_info = {
                            'order_id': result['order_id'],
                            'symbol': symbol,
                            'order_type': order_type.lower(),
                            'side': side.lower(),
                            'quantity': str(quantity),
                            'price': str(price) if price else None,
                            'status': result.get('status', 'pending'),
                            'filled_quantity': result.get('filled_quantity', '0'),
                            'remaining_quantity': result.get('remaining_quantity', str(quantity)),
                            'timestamp': result.get('timestamp', '')
                        }
                        st.session_state.active_orders.append(order_info)
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    st.divider()
    
    # Active Orders Section
    with st.container():
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.subheader("Active Orders")
        with col_header2:
            if st.button("🔄 Refresh Status", type="secondary"):
                with st.spinner("Refreshing order statuses..."):
                    refresh_order_statuses()
                st.success("✅ Orders refreshed!")
                time.sleep(0.5)  # Brief pause to show success message
                st.rerun()
        
        if st.session_state.active_orders:
            # Header row
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
            with col1:
                st.markdown("**Order ID**")
            with col2:
                st.markdown("**Symbol**")
            with col3:
                st.markdown("**Side**")
            with col4:
                st.markdown("**Type**")
            with col5:
                st.markdown("**Quantity**")
            with col6:
                st.markdown("**Price**")
            with col7:
                st.markdown("**Status**")
            with col8:
                st.markdown("**Action**")
            
            st.divider()
            
            for order in st.session_state.active_orders[-10:]:  # Show last 10
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
                
                with col1:
                    st.text(format_order_id(order.get('order_id', 'N/A')))
                with col2:
                    st.text(order.get('symbol', 'N/A'))
                with col3:
                    side_color = color_by_side(order.get('side', ''))
                    st.markdown(f"<span style='color:{side_color}'>{order.get('side', 'N/A').upper()}</span>", unsafe_allow_html=True)
                with col4:
                    st.text(order.get('order_type', 'N/A').upper())
                with col5:
                    filled = order.get('filled_quantity', '0')
                    total = order.get('quantity', '0')
                    st.text(f"{filled}/{total}")
                with col6:
                    price_val = order.get('price')
                    st.text(format_price(price_val) if price_val else "Market")
                with col7:
                    status = order.get('status', 'N/A').upper()
                    status_color = "#00ff00" if status == "FILLED" else "#ffaa00" if status == "PARTIAL" else "#888888"
                    st.markdown(f"<span style='color:{status_color}'>{status}</span>", unsafe_allow_html=True)
                with col8:
                    if st.button("Cancel", key=f"cancel_{order.get('order_id')}"):
                        try:
                            api_client.cancel_order(order['order_id'], order['symbol'])
                            st.success("✅ Order cancelled")
                            # Update status in session state
                            order['status'] = 'cancelled'
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {str(e)}")
        else:
            st.info("No active orders")
    
    # Auto-refresh the page every 3 seconds to update order statuses
    if st.session_state.active_orders:
        time.sleep(3)
        st.rerun()

elif page == "Order Book":
    st.title("📊 Order Book")
    
    # Symbol selector
    symbol = st.selectbox("Select Symbol", ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"], key="ob_symbol")
    
    # Fetch order book
    try:
        orderbook = api_client.get_orderbook(symbol, levels=10)
        st.session_state.orderbook_data = orderbook
        
        # Display BBO
        bbo = orderbook.get('bbo', {})
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Best Bid", format_price(bbo.get('best_bid', 0)))
        with col2:
            spread = bbo.get('spread')
            st.metric("Spread", format_price(spread) if spread else "N/A")
        with col3:
            st.metric("Best Ask", format_price(bbo.get('best_ask', 0)))
        
        st.divider()
        
        # Order book display
        col_bids, col_asks = st.columns(2)
        
        with col_bids:
            st.subheader("🟢 Bids")
            bids = orderbook.get('bids', [])
            if bids:
                for bid in bids:
                    # bid is a list: [price, quantity]
                    price = float(bid[0]) if len(bid) > 0 else 0
                    qty = float(bid[1]) if len(bid) > 1 else 0
                    total = calculate_total(price, qty)
                    st.write(f"**{format_price(price)}** | {format_quantity(qty)} | {format_price(total)}")
            else:
                st.info("No bids")
        
        with col_asks:
            st.subheader("🔴 Asks")
            asks = orderbook.get('asks', [])
            if asks:
                for ask in asks:
                    # ask is a list: [price, quantity]
                    price = float(ask[0]) if len(ask) > 0 else 0
                    qty = float(ask[1]) if len(ask) > 1 else 0
                    total = calculate_total(price, qty)
                    st.write(f"**{format_price(price)}** | {format_quantity(qty)} | {format_price(total)}")
            else:
                st.info("No asks")
        
    except Exception as e:
        st.error(f"Failed to load order book: {str(e)}")

elif page == "Metrics":
    st.title("📈 Performance Metrics")
    
    try:
        stats = api_client.get_statistics()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Orders Processed", stats.get('orders_processed', 0))
        with col2:
            st.metric("Trades Executed", stats.get('trades_executed', 0))
        with col3:
            st.metric("Total Volume", format_quantity(stats.get('total_volume', 0)))
        with col4:
            st.metric("Orders Filled", stats.get('orders_filled', 0))
        
        st.divider()
        
        # Additional stats
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Order Statistics")
            st.write(f"Partial Fills: {stats.get('orders_partial', 0)}")
            st.write(f"Cancelled: {stats.get('orders_cancelled', 0)}")
        
        with col2:
            st.subheader("System Health")
            st.write("✅ Matching Engine: Active")
            st.write(f"✅ Orders in Queue: {stats.get('orders_processed', 0)}")
        
    except Exception as e:
        st.error(f"Failed to load metrics: {str(e)}")

# Auto-refresh
if st.session_state.get('connected') and locals().get('auto_refresh'):
    time.sleep(locals().get('refresh_interval', 3))
    st.rerun()
