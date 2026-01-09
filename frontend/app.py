"""
Voice Agent POC - Streamlit Frontend
A beautiful chat interface with voice support.
"""
import streamlit as st
import requests
import json
from datetime import datetime
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Page config
st.set_page_config(
    page_title="Voice Agent POC",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful UI
st.markdown("""
<style>
    /* Main container */
    .main {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    
    /* Chat messages */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 20px 20px 5px 20px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 20px 20px 20px 5px;
        margin: 0.5rem 0;
        max-width: 80%;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    
    /* Tool calls */
    .tool-call {
        background: rgba(46, 213, 115, 0.1);
        border-left: 3px solid #2ed573;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 10px 10px 0;
        font-family: monospace;
        font-size: 0.85rem;
    }
    
    /* Sources */
    .source-citation {
        background: rgba(255, 193, 7, 0.1);
        border-left: 3px solid #ffc107;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 10px 10px 0;
        font-size: 0.85rem;
    }
    
    /* Voice button */
    .voice-btn {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        color: white;
        border: none;
        padding: 1rem 2rem;
        border-radius: 50px;
        font-size: 1.2rem;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .voice-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 20px rgba(255, 107, 107, 0.4);
    }
    
    /* Status indicator */
    .status-online {
        color: #2ed573;
    }
    
    .status-offline {
        color: #ff6b6b;
    }
    
    /* Header */
    .header-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background: #1a1a2e;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Backend URL
BACKEND_URL = "http://localhost:8000"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")


def check_backend_health():
    """Check if backend is running."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def send_message(message: str) -> dict:
    """Send a message to the backend and get response."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/chat/completions",
            json={
                "messages": [{"role": "user", "content": message}],
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Make sure it's running on port 8000."}
    except Exception as e:
        return {"error": str(e)}


def transcribe_audio(audio_bytes: bytes) -> str:
    """Send audio to backend for transcription."""
    try:
        files = {"audio": ("audio.wav", audio_bytes, "audio/wav")}
        response = requests.post(
            f"{BACKEND_URL}/api/voice/transcribe",
            files=files,
            timeout=120  # Increased timeout for first-time model loading
        )
        response.raise_for_status()
        return response.json().get("text", "")
    except requests.exceptions.Timeout:
        st.error("Transcription timed out. The Whisper model may be loading for the first time. Please try again.")
        return ""
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return ""


def synthesize_speech(text: str) -> bytes:
    """Get audio from backend TTS."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/voice/synthesize",
            json={"text": text},
            timeout=30
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None


# Sidebar
with st.sidebar:
    st.markdown("### 🎙️ Voice Agent POC")
    st.markdown("---")
    
    # Backend status
    backend_online = check_backend_health()
    status_icon = "🟢" if backend_online else "🔴"
    status_text = "Online" if backend_online else "Offline"
    st.markdown(f"**Backend Status:** {status_icon} {status_text}")
    
    if not backend_online:
        st.warning("⚠️ Backend is not running. Start it with:\n```\ncd backend\nuvicorn app.main:app --reload\n```")
    
    st.markdown("---")
    
    # Settings
    st.markdown("### ⚙️ Settings")
    
    voice_enabled = st.checkbox("Enable Voice", value=True)
    auto_play_response = st.checkbox("Auto-play Responses", value=False)
    
    st.markdown("---")
    
    # Quick actions
    st.markdown("### 🚀 Quick Actions")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("📚 Index Documents", use_container_width=True):
        with st.spinner("Indexing documents..."):
            try:
                response = requests.post(f"{BACKEND_URL}/api/documents/index", timeout=60)
                if response.status_code == 200:
                    st.success("Documents indexed!")
                else:
                    st.error("Failed to index documents")
            except:
                st.error("Backend not available")
    
    st.markdown("---")
    
    # Sample queries organized by category
    st.markdown("### 💬 Example Prompts")
    
    st.markdown("#### 📋 Order Lookup")
    order_queries = [
        "Where's my order ORD-10003?",
        "Check status of order ORD-10007",
    ]
    for query in order_queries:
        if st.button(query, use_container_width=True, key=f"sample_{hash(query)}"):
            st.session_state.pending_query = query
    
    st.markdown("#### 💳 Transactions")
    transaction_queries = [
        "Cancel order ORD-10009",
        "I need a refund for order ORD-10003 - wrong item",
        "Apply discount code SAVE20 to order ORD-10010",
        "Expedite shipping for order ORD-10007",
    ]
    for query in transaction_queries:
        if st.button(query, use_container_width=True, key=f"sample_{hash(query)}"):
            st.session_state.pending_query = query
    
    st.markdown("#### 👤 Customer Service")
    customer_queries = [
        "Look up customer CUST-1002",
        "Add 500 loyalty points to customer CUST-1003 as apology",
        "Update my phone number to 555-999-1234 for CUST-1001",
        "Change shipping address for ORD-10003 to 999 New Street, Portland, OR",
    ]
    for query in customer_queries:
        if st.button(query, use_container_width=True, key=f"sample_{hash(query)}"):
            st.session_state.pending_query = query
    
    st.markdown("#### 📚 Knowledge Base")
    kb_queries = [
        "What's your return policy?",
        "How long does shipping take?",
        "Tell me about the wireless headphones",
    ]
    for query in kb_queries:
        if st.button(query, use_container_width=True, key=f"sample_{hash(query)}"):
            st.session_state.pending_query = query
    
    st.markdown("---")
    st.markdown("### 📊 Test Data")
    with st.expander("View Test Data"):
        st.markdown("""
        **Customers:**
        - `CUST-1001` - John Smith (Silver)
        - `CUST-1002` - Sarah Johnson (Gold)
        - `CUST-1003` - Michael Chen (Bronze)
        - `CUST-1004` - Emily Davis (Platinum)
        - `CUST-1005` - Robert Wilson (New)
        - `CUST-1006` - Jennifer Martinez (Silver)
        
        **Orders (Processing - can modify):**
        - `ORD-10003` - Sarah's order ($249.98)
        - `ORD-10007` - Emily's order ($449.98)
        - `ORD-10009` - Robert's order ($179.98)
        - `ORD-10010` - Jennifer's order ($359.97)
        
        **Discount Codes:**
        - `WELCOME10` - 10% off (min $50)
        - `SAVE20` - $20 off (min $100)
        - `VIP25` - 25% off for VIP
        - `FREESHIP` - $15 off (min $75)
        - `HOLIDAY30` - 30% off (min $150)
        """)

# Main content
st.markdown('<h1 class="header-title">🎙️ Voice Agent</h1>', unsafe_allow_html=True)
st.markdown("*A Sierra AI-inspired conversational AI with voice, RAG, and tool execution*")
st.markdown("---")

# Chat container
chat_container = st.container()

with chat_container:
    # Display messages
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        
        if role == "user":
            st.markdown(f'<div class="user-message">🧑 {content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-message">🤖 {content}</div>', unsafe_allow_html=True)
            
            # Show tool calls if any
            if "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    tc_name = tc.get("name", "unknown")
                    tc_args = tc.get("args", {})
                    st.markdown(f'<div class="tool-call">🔧 Called: {tc_name}({tc_args})</div>', unsafe_allow_html=True)
            
            # Show sources if any
            if "sources" in msg and msg["sources"]:
                sources = ", ".join(msg["sources"]) if isinstance(msg["sources"], list) else str(msg["sources"])
                st.markdown(f'<div class="source-citation">📄 Sources: {sources}</div>', unsafe_allow_html=True)

# Play audio if available
if "last_audio" in st.session_state and st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mpeg")
    st.session_state.last_audio = None  # Clear after playing

# Input area
st.markdown("---")

col1, col2 = st.columns([6, 1])

with col1:
    user_input = st.text_input(
        "Message",
        placeholder="Type your message here...",
        key="user_input",
        label_visibility="collapsed"
    )

with col2:
    if voice_enabled:
        # Voice recording button
        try:
            from audio_recorder_streamlit import audio_recorder
            audio_bytes = audio_recorder(
                text="",
                recording_color="#ff6b6b",
                neutral_color="#667eea",
                icon_size="2x",
                key="voice_recorder"
            )
            if audio_bytes and len(audio_bytes) > 1000:  # Ensure meaningful audio
                # Check if this is new audio (not already processed)
                audio_hash = hash(audio_bytes)
                if "last_audio_hash" not in st.session_state or st.session_state.last_audio_hash != audio_hash:
                    st.session_state.last_audio_hash = audio_hash
                    with st.spinner("🎤 Transcribing..."):
                        transcribed = transcribe_audio(audio_bytes)
                        if transcribed:
                            st.session_state.pending_query = transcribed
                            st.rerun()
        except ImportError as e:
            if st.button("🎤", help="Voice input"):
                st.info("Voice recording unavailable. Run: pip install audio-recorder-streamlit")

# Handle pending query from sample buttons
if hasattr(st.session_state, 'pending_query') and st.session_state.pending_query:
    user_input = st.session_state.pending_query
    st.session_state.pending_query = None

# Process input
if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get response
    with st.spinner("Thinking..."):
        response = send_message(user_input)
    
    if "error" in response:
        st.error(response["error"])
        assistant_msg = {"role": "assistant", "content": f"Error: {response['error']}"}
    else:
        content = response.get("message", {}).get("content", response.get("content", "No response"))
        assistant_msg = {"role": "assistant", "content": content}
        
        # Add tool calls if present
        if "tool_calls" in response:
            assistant_msg["tool_calls"] = response["tool_calls"]
        
        # Add sources if present
        if "sources" in response:
            assistant_msg["sources"] = response["sources"]
    
    st.session_state.messages.append(assistant_msg)
    
    # Store last response for TTS
    st.session_state.last_response = assistant_msg["content"]
    
    # Auto-play response
    if auto_play_response and voice_enabled and "error" not in response:
        try:
            audio = synthesize_speech(assistant_msg["content"][:500])  # Limit text length
            if audio:
                st.session_state.last_audio = audio
        except Exception as e:
            pass  # TTS failed silently
    
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8rem;">
    <p>🔧 Built with Streamlit | 🤖 Powered by Ollama + LangChain | 📚 RAG with ChromaDB</p>
    <p>Option A: Lightweight / Learning-Focused Stack</p>
</div>
""", unsafe_allow_html=True)

