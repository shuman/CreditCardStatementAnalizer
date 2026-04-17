#!/bin/bash

# Personal Finance Intelligence - Setup Script
# Automated setup for development environment

set -euo pipefail

echo "🚀 Personal Finance Intelligence - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "✓ Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ required. Found: $python_version"
    exit 1
fi
echo "   Found Python $python_version ✓"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "   Created .venv ✓"
else
    echo "   .venv already exists ✓"
fi
echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate
echo "   Activated ✓"
echo ""

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "   Upgraded pip ✓"
echo ""

# Install dependencies
echo "📥 Installing dependencies..."
echo "   This may take a few minutes..."
pip install -r requirements.txt > /dev/null 2>&1
echo "   Installed all dependencies ✓"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p static/uploads
mkdir -p static/models
mkdir -p templates
echo "   Directories created ✓"
echo ""

# Check if database exists
if [ ! -f "statements.db" ]; then
    echo "💾 Database not found - will be created on first run"
else
    echo "💾 Database found: statements.db ✓"
fi
echo ""

# Create .env file if doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from .env.example..."
    cp .env.example .env
    echo "   Created .env from template ✓"
else
    echo "⚙️  .env already exists ✓"
fi
echo ""

echo "✅ Setup completed successfully!"
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Start the application:"
echo "   bash run.sh"
echo ""
echo "3. Open your browser:"
echo "   http://localhost:8000"
echo ""
echo "4. Upload your first statement and categorize some transactions"
echo ""
echo "5. Configure secrets and OAuth values in .env before production deployment"
echo ""
echo "📚 Documentation:"
echo "   - README.md - Full documentation"
echo "   - CONTRIBUTING.md - Contribution guide"
echo "   - SECURITY.md - Security reporting and best practices"
echo ""
echo "🎉 Happy coding!"
