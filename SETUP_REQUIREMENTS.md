# Setup Requirements & Troubleshooting

## Python Version Compatibility

### Supported Versions
- ✅ **Python 3.11** (supported)
- ✅ **Python 3.12** (recommended)
- ✅ **Python 3.13** (supported)
- ❌ **Python 3.14+** (not yet supported)

### Why Python 3.14+ Doesn't Work

Python 3.14 was released very recently (January 2025) and many core dependencies haven't been updated yet:

- **PyYAML** (required by langchain) fails to build from source with the error:
  ```
  AttributeError: cython_sources
  ```
- Pre-built wheels are not available for Python 3.14 yet
- Other dependencies may also have compatibility issues

### Automatic Detection

The `./run.sh setup` script now automatically:

1. **Tries Python 3.12 first** (most stable)
   ```bash
   python3.12 -m venv venv
   ```

2. **Falls back to Python 3.11** if 3.12 isn't available
   ```bash
   python3.11 -m venv venv
   ```

3. **Checks default python3 version** and validates compatibility
   ```bash
   python3 --version  # Must be 3.11-3.13
   ```

4. **Provides helpful error messages** if Python 3.14+ is detected:
   ```
   ❌ Python 3.14+ detected but not fully compatible with all dependencies
   ⚠️  Please install Python 3.11, 3.12, or 3.13:
      brew install python@3.12  # macOS
      pyenv install 3.12        # Using pyenv
   ```

## Installing the Correct Python Version

### macOS (using Homebrew)

```bash
# Install Python 3.12 (recommended)
brew install python@3.12

# Verify installation
python3.12 --version
```

### Using pyenv (Cross-platform)

```bash
# Install pyenv (if not already installed)
curl https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12

# Set it as the local version for this project
cd /path/to/voice-agent-poc
pyenv local 3.12

# Verify
python --version  # Should show 3.12.x
```

The project includes a `.python-version` file that pyenv will automatically use.

### Linux (Ubuntu/Debian)

```bash
# Add deadsnakes PPA (for newer Python versions)
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# Verify installation
python3.12 --version
```

## Fixing Existing Installation

If you already tried setup with Python 3.14 and it failed:

```bash
# 1. Remove the broken virtual environment
rm -rf backend/venv

# 2. Install Python 3.12 (see above)

# 3. Run setup again
./run.sh setup

# The script will now automatically use Python 3.12
```

## Verifying Your Setup

After running `./run.sh setup`, verify everything worked:

```bash
# Check Python version in virtual environment
cd backend
source venv/bin/activate
python --version  # Should show 3.11.x or 3.12.x or 3.13.x

# Check if key packages installed correctly
python -c "import langchain; print('LangChain:', langchain.__version__)"
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import yaml; print('PyYAML: OK')"
```

## Common Issues

### Issue 1: "python3.12: command not found"

**Solution**: Python 3.12 is not installed. Install it using one of the methods above.

### Issue 2: "Permission denied" when creating venv

**Solution**: 
```bash
# Make sure you have write permissions
cd backend
python3.12 -m venv venv
```

### Issue 3: Setup works but imports fail

**Solution**: Make sure you're activating the virtual environment:
```bash
cd backend
source venv/bin/activate  # Always activate before running Python code
```

### Issue 4: "No module named 'pip'"

**Solution**: 
```bash
# Reinstall pip in the virtual environment
python3.12 -m ensurepip --upgrade
python3.12 -m pip install --upgrade pip
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `./run.sh setup` | Create venv and install dependencies (auto-detects Python) |
| `python3.12 --version` | Check if Python 3.12 is installed |
| `rm -rf backend/venv` | Remove virtual environment |
| `source backend/venv/bin/activate` | Activate virtual environment |
| `deactivate` | Deactivate virtual environment |

## For Contributors

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed development setup instructions, including:
- Python version management with pyenv
- Virtual environment best practices
- Dependency management
- Testing and code quality tools


