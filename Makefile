# Voice Agent POC - Makefile

.PHONY: setup start backend frontend index seed test clean help check-ollama pull-model

# Default target
help:
	@echo "Voice Agent POC - Available Commands"
	@echo ""
	@echo "  make setup     - Install dependencies and configure"
	@echo "  make start     - Start both backend and frontend"
	@echo "  make backend   - Start backend only"
	@echo "  make frontend  - Start frontend only"
	@echo "  make index     - Index documents for RAG"
	@echo "  make seed      - Seed database with sample data"
	@echo "  make test      - Test API endpoints"
	@echo "  make clean     - Clean up generated files"
	@echo "  make pull-model - Pull Llama 3.2 model"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make setup"
	@echo "  2. ollama serve (in another terminal)"
	@echo "  3. make pull-model"
	@echo "  4. make start"

# Setup project
setup:
	@./run.sh setup

# Start everything
start:
	@./run.sh start

# Start backend only
backend:
	@./run.sh backend

# Start frontend only
frontend:
	@./run.sh frontend

# Index documents
index:
	@./run.sh index

# Seed database
seed:
	@./run.sh seed

# Test endpoints
test:
	@./run.sh test

# Clean up
clean:
	@./run.sh clean

# Check Ollama status
check-ollama:
	@echo "🔍 Checking Ollama..."
	@curl -s http://localhost:11434/api/tags | python3 -m json.tool || echo "❌ Ollama not running. Start with: ollama serve"

# Pull LLM model
pull-model:
	@echo "📥 Pulling Llama 3.2 model..."
	@ollama pull llama3.2
