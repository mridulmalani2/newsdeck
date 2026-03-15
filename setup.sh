#!/bin/bash
# ============================================================
# News Article Slide Automation - Setup Script (macOS)
# ============================================================

set -e

echo "============================================"
echo "  Article Automation System Setup"
echo "============================================"
echo ""

# Check Python version
echo "Checking Python..."
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3 not found. Install it: brew install python3"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | grep -oP '3\.\d+')
echo "✓ Python: $($PYTHON --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
$PYTHON -m venv .venv
source .venv/bin/activate
echo "✓ Virtual environment created"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Install Playwright browsers
echo ""
echo "Installing Playwright browsers..."
playwright install chromium
echo "✓ Chromium browser installed"

# Create output directories
echo ""
echo "Creating directories..."
mkdir -p slides logs cache
echo "✓ Directories created"

# Setup .env from template
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env file created from template."
    echo "   Edit .env with your actual values:"
    echo "   - NOTION_API_KEY"
    echo "   - NOTION_DATABASE_ID"
    echo "   - SLIDES_OUTPUT_DIR (your Desktop/slides path)"
    echo ""
else
    echo "✓ .env file already exists"
fi

# Create Desktop/slides directory
SLIDES_DIR=$(grep SLIDES_OUTPUT_DIR .env 2>/dev/null | cut -d'=' -f2 || echo "")
if [ -n "$SLIDES_DIR" ] && [ "$SLIDES_DIR" != "your_slides_dir_here" ]; then
    mkdir -p "$SLIDES_DIR"
    echo "✓ Slides output directory: $SLIDES_DIR"
fi

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Edit .env with your Notion credentials:"
echo "     nano .env"
echo ""
echo "  2. Start the server:"
echo "     source .venv/bin/activate"
echo "     python main.py"
echo ""
echo "  3. Test with a sample slide:"
echo "     curl -X POST http://localhost:8000/test"
echo ""
echo "  4. Process all unprocessed articles:"
echo "     curl -X POST http://localhost:8000/process/batch"
echo ""
echo "  5. (Optional) Auto-start on boot:"
echo "     - Edit com.exa.article-automation.plist with your paths"
echo "     - cp com.exa.article-automation.plist ~/Library/LaunchAgents/"
echo "     - launchctl load ~/Library/LaunchAgents/com.exa.article-automation.plist"
echo ""
echo "  Health check: http://localhost:8000/health"
echo "  API docs:     http://localhost:8000/docs"
echo ""
