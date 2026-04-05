# 🎙️ Voice Agent POC

A **Sierra AI-inspired** conversational AI system with voice support, RAG, and tool execution.

Built with **Option A: Lightweight / Learning-Focused Stack** - runs entirely locally!

## 🚀 Quick Start

```bash
# 1. Install Ollama
brew install ollama  # macOS
ollama serve &
ollama pull llama3.2

# 2. Setup project
make setup
# OR: ./run.sh setup

# 3. Start application
make start
# OR: ./run.sh start
```

**Open**: http://localhost:8501 🎉

> **Requirements:** Python 3.11-3.13 (3.12 recommended). If Python 3.14+, see [troubleshooting](#-troubleshooting).

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 **Chat Interface** | Streamlit-based chat with beautiful UI |
| 🎤 **Voice Input** | Speech-to-text using local Whisper |
| 🔊 **Voice Output** | Text-to-speech using local TTS |
| 📚 **RAG** | Document-grounded responses with ChromaDB |
| 🔧 **Tool Execution** | Natural language database operations |
| 🛡️ **Guardrails** | Safe, controlled agent behavior |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│         (Chat UI + Voice Recording + Document Upload)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Agent     │  │    RAG      │  │      Voice          │  │
│  │ Orchestrator│  │  Pipeline   │  │  (Whisper + TTS)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │                   │                    │
        ▼                   ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Ollama    │     │  ChromaDB   │     │   SQLite    │
│ (Llama 3.2) │     │  (Vectors)  │     │    (DB)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Voice Flow (HTTP, not WebRTC)

```
┌──────────────┐  audio bytes   ┌──────────────┐  .wav file  ┌──────────────┐
│   Browser    │ ──────────────▶│   FastAPI    │ ──────────▶ │   Whisper    │
│  (mic input) │   POST /api/   │   Backend    │             │    Model     │
└──────────────┘   transcribe   └──────────────┘             └──────┬───────┘
                                                                    │ text
       ┌────────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐  base64 mp3    ┌──────────────┐   text      ┌──────────────┐
│   Browser    │ ◀──────────────│   FastAPI    │ ◀────────── │    gTTS      │
│ <audio> play │   POST /api/   │   Backend    │             │   Engine     │
└──────────────┘   synthesize   └──────────────┘             └──────────────┘
```

> **Note**: This is simple REST-based voice (record → upload → process → download).
> For real-time bidirectional audio, you'd use WebRTC or WebSockets.

## 📁 Project Structure

```
voice-agent-poc/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry
│   │   ├── config.py        # Configuration
│   │   ├── api/routes/      # REST endpoints
│   │   ├── core/            # Agent orchestration
│   │   │   ├── agent.py     # Main agent
│   │   │   └── llm.py       # LLM client (Ollama)
│   │   ├── rag/             # RAG pipeline
│   │   │   ├── embeddings.py
│   │   │   ├── chunker.py
│   │   │   ├── vectorstore.py
│   │   │   └── retriever.py
│   │   ├── voice/           # Voice processing
│   │   │   ├── stt.py       # Whisper STT
│   │   │   └── tts.py       # Local TTS
│   │   ├── tools/           # Agent tools
│   │   │   ├── registry.py
│   │   │   └── executor.py
│   │   └── db/              # Database
│   │       ├── models.py
│   │       ├── operations.py
│   │       └── seed.py
│   └── requirements.txt
├── frontend/
│   └── app.py               # Streamlit UI
├── data/
│   ├── documents/           # Documents for RAG
│   ├── db/                  # SQLite database
│   └── chroma/              # Vector store
├── run.sh                   # Run script
├── PROJECT_PLAN.md          # Full strategic plan
└── MODELS_AND_FRAMEWORKS.md # Technology comparisons
```

## 🔧 Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| **Frontend** | Streamlit | Rapid prototyping |
| **Backend** | FastAPI | Modern, async |
| **LLM** | Ollama + Llama 3.2 | Local, free |
| **STT** | Whisper (local) | Industry standard |
| **TTS** | pyttsx3 | Offline, cross-platform |
| **RAG** | LangChain | Well-documented |
| **Vector DB** | ChromaDB | Simple, embedded |
| **Database** | SQLite | Zero config |
| **Embeddings** | sentence-transformers | Local, fast |

## 💬 Demo Scenarios

### 1. Policy Questions (RAG)
```
User: "What's your return policy?"
Agent: [Searches documents] "Our return policy allows returns within 30 days..."
```

### 2. Order Lookup (Tool Execution)
```
User: "Where's my order ORD-10001?"
Agent: [Calls lookup_order] "Your order ORD-10001 was delivered on..."
```

### 3. Refund Processing
```
User: "I want a refund for my order"
Agent: "I can help with that. Which order would you like to refund?"
```

### 4. Voice Interaction
```
User: [Speaks] "What's the battery life of the headphones?"
Agent: [Speaks] "The wireless headphones have up to 30 hours of battery..."
```

## 📚 Sample Documents

The project includes sample documents in `data/documents/`:
- `return_policy.md` - Return and refund policies
- `shipping_info.md` - Shipping options and tracking
- `product_faq.md` - Product FAQs and specifications

## 🗃️ Sample Data

The database is seeded with:
- 5 customers
- 8 products
- 7 orders with items

## 🛠️ Commands

**Using Make (recommended):**
```bash
make setup      # Install dependencies
make start      # Start backend + frontend
make backend    # Start backend only
make frontend   # Start frontend only
make index      # Index documents
make seed       # Seed database
make test       # Test API endpoints
make clean      # Clean up
make pull-model # Pull Llama 3.2 model
```

**Or using shell script directly:**
```bash
./run.sh setup      # Install dependencies
./run.sh start      # Start backend + frontend
./run.sh backend    # Start backend only
./run.sh frontend   # Start frontend only
./run.sh index      # Index documents
./run.sh seed       # Seed database
./run.sh test       # Test API endpoints
./run.sh clean      # Clean up
```

> **Tip:** Use `make` if you have it (standard on macOS/Linux). Otherwise `./run.sh` works everywhere.

## 🔍 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/chat/completions` | POST | Chat with agent |
| `/api/documents/upload` | POST | Upload document |
| `/api/documents/index` | POST | Index all documents |
| `/api/voice/transcribe` | POST | Speech-to-text |
| `/api/voice/synthesize` | POST | Text-to-speech |

## 📖 Learning Resources

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for:
- Detailed architecture
- Key concepts to learn
- Development phases
- Experiment ideas

See [MODELS_AND_FRAMEWORKS.md](./MODELS_AND_FRAMEWORKS.md) for:
- Model comparisons
- Framework options
- Cost estimates

## 🎯 For Sierra AI Demo

This POC demonstrates understanding of:
1. **Agent Architecture** - Tool calling, multi-turn conversations
2. **RAG Pipeline** - Document chunking, embeddings, retrieval
3. **Voice AI** - STT/TTS integration
4. **Reliability** - Confirmation flows, error handling
5. **Production Patterns** - Modular design, logging, configuration

## 🔧 Troubleshooting

### Python Version Issues

**Problem**: `make setup` fails with PyYAML build errors

**Solution**: You're likely using Python 3.14+, which isn't fully supported yet. Install Python 3.12:

```bash
# macOS
brew install python@3.12

# Using pyenv
pyenv install 3.12
pyenv local 3.12

# Then recreate the virtual environment
rm -rf backend/venv
./run.sh setup
```

### Ollama Connection Issues

**Problem**: "Ollama is not running" error

**Solution**:
```bash
# Start Ollama in a separate terminal
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

### Voice Input Issues

**Problem**: Microphone not working

**Solution**: Ensure your browser has microphone permissions enabled and you're using HTTPS or localhost.

### Missing Dependencies

**Problem**: Import errors when starting the app

**Solution**:
```bash
# Reinstall dependencies
cd backend
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Detailed Setup Help

For comprehensive setup instructions, Python version management, and additional troubleshooting, see:
- [SETUP_REQUIREMENTS.md](./SETUP_REQUIREMENTS.md) - Detailed setup guide
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Development guidelines

---

Built with ❤️ for learning and experimentation.
