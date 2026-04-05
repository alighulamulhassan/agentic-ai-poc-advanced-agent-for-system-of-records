#!/bin/bash
# Test script to simulate new user experience

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🧪 Testing New User Experience${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Function to run test
run_test() {
    local test_name=$1
    local test_cmd=$2
    
    echo -e "\n${YELLOW}▶ Test: $test_name${NC}"
    echo -e "${BLUE}Command: $test_cmd${NC}\n"
    
    if eval "$test_cmd"; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        return 1
    fi
}

# Test 1: Clean state
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 1: Simulating Fresh Clone${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Cleaning up existing setup...${NC}"
rm -rf backend/venv
rm -rf backend/.env
echo -e "${GREEN}✅ Cleaned up (simulating fresh git clone)${NC}"

# Test 2: Check Python detection
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 2: Python Version Detection${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Checking available Python versions:${NC}"
for py_cmd in python3.12 python3.11 python3.13 python3; do
    if command -v $py_cmd &> /dev/null; then
        version=$($py_cmd --version 2>&1)
        echo -e "  ${GREEN}✓${NC} $py_cmd: $version"
    else
        echo -e "  ${RED}✗${NC} $py_cmd: not found"
    fi
done

# Test 3: Run setup
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 3: Running Setup (Fresh Install)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Running: make setup${NC}\n"
make setup

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Setup completed successfully${NC}"
else
    echo -e "\n${RED}❌ Setup failed${NC}"
    exit 1
fi

# Test 4: Verify virtual environment
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 4: Verifying Virtual Environment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

if [ -d "backend/venv" ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
    
    # Activate and check Python version
    cd backend
    source venv/bin/activate
    PYTHON_VERSION=$(python --version)
    echo -e "${GREEN}✅ Python version: $PYTHON_VERSION${NC}"
    
    # Check if it's a supported version
    if echo "$PYTHON_VERSION" | grep -qE "3\.(11|12|13)"; then
        echo -e "${GREEN}✅ Python version is compatible (3.11-3.13)${NC}"
    else
        echo -e "${RED}❌ Python version is not in supported range${NC}"
        exit 1
    fi
    
    cd ..
else
    echo -e "${RED}❌ Virtual environment not created${NC}"
    exit 1
fi

# Test 5: Verify .env file
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 5: Verifying Configuration${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

if [ -f "backend/.env" ]; then
    echo -e "${GREEN}✅ .env file created${NC}"
    echo -e "\n${YELLOW}Contents:${NC}"
    cat backend/.env | sed 's/^/  /'
else
    echo -e "${RED}❌ .env file not created${NC}"
    exit 1
fi

# Test 6: Test package imports
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 6: Testing Package Imports${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

cd backend
source venv/bin/activate

PACKAGES=("langchain" "fastapi" "yaml" "streamlit" "ollama")
ALL_PASSED=true

for package in "${PACKAGES[@]}"; do
    if python -c "import $package" 2>/dev/null; then
        version=$(python -c "import $package; print($package.__version__ if hasattr($package, '__version__') else 'OK')" 2>/dev/null || echo "OK")
        echo -e "${GREEN}✅ $package: $version${NC}"
    else
        echo -e "${RED}❌ Failed to import $package${NC}"
        ALL_PASSED=false
    fi
done

cd ..

if [ "$ALL_PASSED" = false ]; then
    echo -e "\n${RED}❌ Some package imports failed${NC}"
    exit 1
fi

# Test 7: Test idempotency (run setup again)
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test 7: Testing Idempotency (Running Setup Again)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Running: make setup (should detect existing venv)${NC}\n"
make setup

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Idempotency test passed${NC}"
else
    echo -e "\n${RED}❌ Idempotency test failed${NC}"
    exit 1
fi

# Final Summary
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All Tests Passed! New User Experience is Working${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Summary:${NC}"
echo -e "  ${GREEN}✓${NC} Python version detection works"
echo -e "  ${GREEN}✓${NC} Virtual environment created successfully"
echo -e "  ${GREEN}✓${NC} Dependencies installed correctly"
echo -e "  ${GREEN}✓${NC} Configuration files generated"
echo -e "  ${GREEN}✓${NC} All packages importable"
echo -e "  ${GREEN}✓${NC} Setup is idempotent"

echo -e "\n${BLUE}Next Steps for Testing:${NC}"
echo -e "  1. ${YELLOW}./run.sh start${NC} - Test full application startup"
echo -e "  2. ${YELLOW}./run.sh test${NC} - Test API endpoints"
echo -e "  3. Visit ${YELLOW}http://localhost:8501${NC} - Test frontend"

echo ""

