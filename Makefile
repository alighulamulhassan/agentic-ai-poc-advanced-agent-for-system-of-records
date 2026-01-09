# Voice Agent POC - Makefile
# Option A: Lightweight / Learning-Focused Stack

.PHONY: setup start backend frontend index seed test clean help

# Default target
help:
	@echo "Voice Agent POC - Commands"
	@echo ""
	@echo "  make setup     - Install dependencies and configure"
	@echo "  make start     - Start both backend and frontend"
	@echo "  make backend   - Start backend only"
	@echo "  make frontend  - Start frontend only"
	@echo "  make index     - Index documents for RAG"
	@echo "  make seed      - Seed database with sample data"
	@echo "  make test      - Test API endpoints"
	@echo "  make clean     - Clean up generated files"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make setup"
	@echo "  2. ollama serve (in another terminal)"
	@echo "  3. ollama pull llama3.2"
	@echo "  4. make start"

# Setup project
setup:
	@echo "📦 Setting up Voice Agent POC..."
	@./run.sh setup

# Start everything
start:
	@./run.sh start

# Start backend only
backend:
	@echo "🐍 Starting backend..."
	@cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Start frontend only
frontend:
	@echo "🎨 Starting frontend..."
	@cd backend && source venv/bin/activate && cd ../frontend && streamlit run app.py --server.port 8501

# Index documents
index:
	@echo "📚 Indexing documents..."
	@curl -X POST http://localhost:8000/api/documents/index | python3 -m json.tool

# Seed database
seed:
	@echo "🌱 Seeding database..."
	@cd backend && source venv/bin/activate && python -c "from app.db.seed import seed_database; seed_database()"

# Test endpoints
test:
	@./run.sh test

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf backend/venv
	@rm -rf data/db/*.db
	@rm -rf data/chroma
	@rm -rf __pycache__ */__pycache__ */*/__pycache__
	@echo "✅ Done!"

# Install only backend deps
install-backend:
	@echo "📦 Installing backend dependencies..."
	@cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Check Ollama
check-ollama:
	@echo "🔍 Checking Ollama..."
	@curl -s http://localhost:11434/api/tags | python3 -m json.tool || echo "Ollama not running. Start with: ollama serve"

# Pull LLM model
pull-model:
	@echo "📥 Pulling Llama 3.2..."
	@ollama pull llama3.2
