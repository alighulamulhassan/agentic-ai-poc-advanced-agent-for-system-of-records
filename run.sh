#!/bin/bash
# Voice Agent POC - Run Script
# Option A: Lightweight / Learning-Focused Stack

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           🎙️  Voice Agent POC - Lightweight Stack             ║"
echo "║        Sierra AI-inspired conversational AI system            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    fi
    echo -e "${GREEN}✅ $1 found${NC}"
    return 0
}

# Function to check if Ollama is running
check_ollama() {
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is running${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Ollama is not running${NC}"
        return 1
    fi
}

# Parse arguments
ACTION=${1:-"help"}

case $ACTION in
    "setup")
        echo -e "\n${BLUE}📦 Setting up the project...${NC}\n"
        
        # Check Python and find compatible version
        PYTHON_CMD=""
        
        # Try Python 3.12 first (recommended)
        if command -v python3.12 &> /dev/null; then
            PYTHON_VERSION=$(python3.12 --version | cut -d' ' -f2)
            echo -e "${GREEN}✅ Found Python 3.12 ($PYTHON_VERSION)${NC}"
            PYTHON_CMD="python3.12"
        # Try Python 3.11
        elif command -v python3.11 &> /dev/null; then
            PYTHON_VERSION=$(python3.11 --version | cut -d' ' -f2)
            echo -e "${GREEN}✅ Found Python 3.11 ($PYTHON_VERSION)${NC}"
            PYTHON_CMD="python3.11"
        # Check default python3 version
        elif command -v python3 &> /dev/null; then
            PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
            MAJOR_MINOR=$(echo $PYTHON_VERSION | sed 's/\.//g')
            
            if [ "$MAJOR_MINOR" -ge "311" ] && [ "$MAJOR_MINOR" -le "313" ]; then
                echo -e "${GREEN}✅ Found Python $PYTHON_VERSION${NC}"
                PYTHON_CMD="python3"
            elif [ "$MAJOR_MINOR" -ge "314" ]; then
                echo -e "${RED}❌ Python 3.14+ detected but not fully compatible with all dependencies${NC}"
                echo -e "${YELLOW}⚠️  Please install Python 3.11, 3.12, or 3.13:${NC}"
                echo -e "   ${BLUE}brew install python@3.12${NC}  # macOS"
                echo -e "   ${BLUE}pyenv install 3.12${NC}       # Using pyenv"
                exit 1
            else
                echo -e "${RED}❌ Python 3.11+ is required (found $PYTHON_VERSION)${NC}"
                exit 1
            fi
        else
            echo -e "${RED}❌ Python 3 is not installed${NC}"
            exit 1
        fi
        
        echo -e "${BLUE}Using: $PYTHON_CMD${NC}"
        
        # Create virtual environment
        if [ ! -d "backend/venv" ]; then
            echo -e "\n${BLUE}Creating virtual environment...${NC}"
            cd backend
            $PYTHON_CMD -m venv venv
            source venv/bin/activate
            pip install --upgrade pip
            pip install -r requirements.txt
            cd ..
            echo -e "${GREEN}✅ Virtual environment created${NC}"
        else
            echo -e "${GREEN}✅ Virtual environment already exists${NC}"
        fi
        
        # Create .env if not exists
        if [ ! -f "backend/.env" ]; then
            echo -e "\n${BLUE}Creating .env file...${NC}"
            cat > backend/.env << 'EOF'
# LLM Settings (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2

# Whisper model: tiny, base, small, medium, large
WHISPER_MODEL=base

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
EOF
            echo -e "${GREEN}✅ .env file created${NC}"
        fi
        
        # Create directories
        mkdir -p data/documents data/db data/audio data/chroma
        
        echo -e "\n${GREEN}✅ Setup complete!${NC}"
        echo -e "\nNext steps:"
        echo -e "  1. Install and start Ollama: ${BLUE}brew install ollama && ollama serve${NC}"
        echo -e "  2. Pull a model: ${BLUE}ollama pull llama3.2${NC}"
        echo -e "  3. Run the app: ${BLUE}./run.sh start${NC}"
        ;;
        
    "start")
        echo -e "\n${BLUE}🚀 Starting Voice Agent POC...${NC}\n"
        
        # Check Ollama
        if ! check_ollama; then
            echo -e "${YELLOW}Starting Ollama...${NC}"
            ollama serve &
            sleep 3
        fi
        
        # Check if model is available
        echo -e "\n${BLUE}Checking LLM model...${NC}"
        if ! ollama list | grep -q "llama3.2"; then
            echo -e "${YELLOW}Pulling llama3.2 model (this may take a while)...${NC}"
            ollama pull llama3.2
        fi
        echo -e "${GREEN}✅ Model ready${NC}"
        
        # Start backend
        echo -e "\n${BLUE}Starting backend server...${NC}"
        cd backend
        source venv/bin/activate
        uvicorn app.main:app --reload --port 8000 &
        BACKEND_PID=$!
        cd ..
        
        # Wait for backend
        echo "Waiting for backend to start..."
        sleep 5
        
        # Index documents
        echo -e "\n${BLUE}Indexing documents...${NC}"
        curl -s -X POST http://localhost:8000/api/documents/index || true
        
        # Start frontend
        echo -e "\n${BLUE}Starting Streamlit frontend...${NC}"
        cd backend
        source venv/bin/activate
        cd ../frontend
        streamlit run app.py --server.port 8501 &
        FRONTEND_PID=$!
        cd ..
        
        echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ Voice Agent POC is running!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "\n   🌐 Frontend: ${BLUE}http://localhost:8501${NC}"
        echo -e "   📡 Backend API: ${BLUE}http://localhost:8000${NC}"
        echo -e "   📚 API Docs: ${BLUE}http://localhost:8000/docs${NC}"
        echo -e "\n   Press Ctrl+C to stop all services\n"
        
        # Wait for Ctrl+C
        trap "echo -e '\n${YELLOW}Stopping services...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
        wait
        ;;
        
    "backend")
        echo -e "\n${BLUE}Starting backend only...${NC}\n"
        cd backend
        source venv/bin/activate
        uvicorn app.main:app --reload --port 8000
        ;;
        
    "frontend")
        echo -e "\n${BLUE}Starting frontend only...${NC}\n"
        cd backend
        source venv/bin/activate
        cd ../frontend
        streamlit run app.py --server.port 8501
        ;;
        
    "index")
        echo -e "\n${BLUE}Indexing documents...${NC}\n"
        curl -X POST http://localhost:8000/api/documents/index | python3 -m json.tool
        ;;
        
    "seed")
        echo -e "\n${BLUE}Seeding database...${NC}\n"
        cd backend
        source venv/bin/activate
        python -c "from app.db.seed import seed_database; seed_database()"
        ;;
        
    "test")
        echo -e "\n${BLUE}Testing the API...${NC}\n"
        
        echo "1. Health check:"
        curl -s http://localhost:8000/health | python3 -m json.tool
        
        echo -e "\n2. Voice status:"
        curl -s http://localhost:8000/api/voice/status | python3 -m json.tool
        
        echo -e "\n3. Document stats:"
        curl -s http://localhost:8000/api/documents/stats | python3 -m json.tool
        
        echo -e "\n4. Test chat:"
        curl -s -X POST http://localhost:8000/api/chat/completions \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "Hello! What can you help me with?"}]}' \
            | python3 -m json.tool
        ;;
        
    "clean")
        echo -e "\n${BLUE}Cleaning up...${NC}\n"
        rm -rf backend/venv
        rm -rf data/db/*.db
        rm -rf data/chroma
        rm -rf __pycache__ */__pycache__ */*/__pycache__
        echo -e "${GREEN}✅ Cleaned up!${NC}"
        ;;
        
    "help"|*)
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Commands:"
        echo "  setup     - Install dependencies and configure the project"
        echo "  start     - Start both backend and frontend"
        echo "  backend   - Start only the backend API server"
        echo "  frontend  - Start only the Streamlit frontend"
        echo "  index     - Index documents in data/documents/"
        echo "  seed      - Seed the database with sample data"
        echo "  test      - Test the API endpoints"
        echo "  clean     - Remove virtual environment and data"
        echo "  help      - Show this help message"
        echo ""
        echo "Quick Start:"
        echo "  1. ./run.sh setup"
        echo "  2. ollama serve  (in another terminal)"
        echo "  3. ollama pull llama3.2"
        echo "  4. ./run.sh start"
        ;;
esac



