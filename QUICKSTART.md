## 🚀 Quick Start Guide

### ✅ Prerequisites Check

Before starting, verify your Python version:

```bash
python3 --version
```

**Supported:** Python 3.11, 3.12, or 3.13 (3.12 recommended)  
**Not supported:** Python 3.14+ (see below for solution)

---

### 📦 Setup (First Time)

```bash
# 1. Make script executable
chmod +x run.sh

# 2. Run setup (auto-detects correct Python version)
./run.sh setup

# 3. Install Ollama
brew install ollama  # macOS
# OR
curl -fsSL https://ollama.com/install.sh | sh  # Linux

# 4. Start Ollama & pull model
ollama serve &
ollama pull llama3.2

# 5. Start the app
./run.sh start
```

Visit: http://localhost:8501 🎉

---

### ⚠️ Python 3.14+ Users

If you have Python 3.14+, install 3.12:

```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv

# Using pyenv (any OS)
pyenv install 3.12
pyenv local 3.12

# Then run setup again
rm -rf backend/venv
./run.sh setup
```

---

### 🔧 Common Commands

```bash
./run.sh start      # Start backend + frontend
./run.sh backend    # Start backend only
./run.sh frontend   # Start frontend only
./run.sh test       # Test API endpoints
./run.sh clean      # Clean up everything
```

---

### ❓ Troubleshooting

**Setup fails?**
- Check Python version: `python3 --version` (must be 3.11-3.13)
- See: [SETUP_REQUIREMENTS.md](SETUP_REQUIREMENTS.md)

**Ollama not running?**
```bash
ollama serve  # Start Ollama
curl http://localhost:11434/api/tags  # Verify
```

**Import errors?**
```bash
cd backend
source venv/bin/activate  # Always activate first!
python -c "import langchain"  # Test imports
```

---

### 📚 Documentation

- **Setup Help:** [SETUP_REQUIREMENTS.md](SETUP_REQUIREMENTS.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Project Plan:** [PROJECT_PLAN.md](PROJECT_PLAN.md)
- **Full README:** [README.md](README.md)

---

### ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 Chat | Streamlit-based conversational UI |
| 🎤 Voice Input | Local Whisper speech-to-text |
| 🔊 Voice Output | Text-to-speech with gTTS |
| 📚 RAG | Document-grounded responses |
| 🔧 Tools | Natural language DB operations |
| 🛡️ Guardrails | Safe, controlled behavior |

---

**Need help?** Open an issue or check the troubleshooting docs!


