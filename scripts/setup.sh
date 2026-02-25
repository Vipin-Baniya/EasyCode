#!/bin/bash
# Setup script for Project Core

echo "🚀 Setting up Project Core..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed."; exit 1; }

# Copy .env if not exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your ANTHROPIC_API_KEY"
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p backend/app/workspaces
mkdir -p logs

# Build Docker images
echo "🐳 Building Docker images..."
docker-compose build

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your ANTHROPIC_API_KEY"
echo "  2. Run: docker-compose up -d"
echo "  3. Access: http://localhost:3000"
