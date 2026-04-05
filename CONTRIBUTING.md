# Contributing to Voice Agent POC

## Development Setup

### Python Version Requirements

This project requires **Python 3.11, 3.12, or 3.13**. Python 3.14+ is not yet supported due to dependency compatibility issues (specifically PyYAML).

#### Recommended: Use Python 3.12

**Option 1: Direct Installation**
```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12 python3.12-venv
```

**Option 2: Using pyenv (Recommended for managing multiple Python versions)**
```bash
# Install pyenv (if not already installed)
curl https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12

# Set it as the local version for this project
cd /path/to/voice-agent-poc
pyenv local 3.12
```

The project includes a `.python-version` file that pyenv will automatically use.

### Initial Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd voice-agent-poc

# Make the run script executable
chmod +x run.sh

# Setup the project (creates venv, installs dependencies)
./run.sh setup
```

### Common Issues and Solutions

#### Issue: PyYAML Build Failures

**Symptom**: `ERROR: Failed to build 'pyyaml' when getting requirements to build wheel`

**Cause**: You're using Python 3.14+, which PyYAML doesn't fully support yet.

**Solution**:
1. Install Python 3.12 (see above)
2. Remove the existing virtual environment: `rm -rf backend/venv`
3. Run setup again: `./run.sh setup`

#### Issue: Virtual Environment Uses Wrong Python

**Solution**:
```bash
# Remove the venv
rm -rf backend/venv

# Explicitly create with desired version
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Development Workflow

1. **Activate the virtual environment**:
   ```bash
   cd backend
   source venv/bin/activate
   ```

2. **Start development servers**:
   ```bash
   # Terminal 1: Ollama
   ollama serve
   
   # Terminal 2: Backend
   ./run.sh backend
   
   # Terminal 3: Frontend
   ./run.sh frontend
   ```

3. **Run tests**:
   ```bash
   ./run.sh test
   ```

### Code Quality

```bash
# Format code
cd backend
source venv/bin/activate
black app/
ruff check app/ --fix

# Type checking (if using mypy)
mypy app/
```

### Project Structure

```
voice-agent-poc/
├── .python-version          # Pyenv version file (3.12)
├── backend/
│   ├── requirements.txt     # Python dependencies
│   ├── venv/               # Virtual environment (gitignored)
│   └── app/                # Application code
├── frontend/
│   └── app.py              # Streamlit UI
├── data/                   # Data files (gitignored)
├── run.sh                  # Main run script
└── Makefile               # Make commands
```

### Adding Dependencies

When adding new Python packages:

1. Add to `backend/requirements.txt`
2. Check compatibility with Python 3.11-3.13
3. Test installation: `pip install -r requirements.txt`
4. Update documentation if needed

### Environment Variables

The project uses a `.env` file in the `backend/` directory:

```bash
# LLM Settings
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2

# Whisper model: tiny, base, small, medium, large
WHISPER_MODEL=base

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

This file is automatically created by `./run.sh setup`.

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=app tests/
```

### Documentation

When contributing, please:
- Update relevant documentation in `README.md`
- Add docstrings to new functions/classes
- Update `PROJECT_PLAN.md` for architectural changes
- Add examples for new features

### Pull Request Guidelines

1. Ensure Python 3.11-3.13 compatibility
2. Follow existing code style (use black formatter)
3. Add tests for new features
4. Update documentation
5. Ensure all tests pass: `./run.sh test`

## Questions?

Open an issue or start a discussion in the repository.


