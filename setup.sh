#!/bin/bash
# Comprehensive setup and validation script for Project Core

set -e  # Exit on error

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Project Core - Setup & Validation   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}━━━ $1 ━━━${NC}"
}

# Function to check command existence
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is NOT installed"
        return 1
    fi
}

# Check prerequisites
print_header "Checking Prerequisites"

MISSING_DEPS=false

if ! check_command docker; then
    MISSING_DEPS=true
fi

if ! check_command docker-compose; then
    if ! check_command "docker compose"; then
        MISSING_DEPS=true
    fi
fi

if [ "$MISSING_DEPS" = true ]; then
    echo -e "\n${RED}ERROR: Missing required dependencies!${NC}"
    echo "Please install Docker and Docker Compose to continue."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check optional tools
echo ""
check_command python3 || echo -e "${YELLOW}  (Optional for local development)${NC}"
check_command node || echo -e "${YELLOW}  (Optional for local development)${NC}"
check_command git || echo -e "${YELLOW}  (Optional for version control)${NC}"

# Create .env if not exists
print_header "Environment Configuration"

if [ ! -f .env ]; then
    echo -e "${YELLOW}! .env file not found${NC}"
    echo "Creating from template..."
    cp .env.example .env
    echo -e "${GREEN}✓${NC} Created .env file"
    echo -e "\n${YELLOW}IMPORTANT:${NC} Please edit .env and add your ANTHROPIC_API_KEY"
    echo "You can get an API key from: https://console.anthropic.com/"
    
    # Prompt for API key
    read -p "Would you like to enter your Anthropic API key now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your Anthropic API key: " api_key
        if [ ! -z "$api_key" ]; then
            # Update .env file
            sed -i.bak "s/ANTHROPIC_API_KEY=your_anthropic_api_key_here/ANTHROPIC_API_KEY=$api_key/" .env
            rm .env.bak
            echo -e "${GREEN}✓${NC} API key configured"
        fi
    fi
else
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check if API key is configured
    if grep -q "ANTHROPIC_API_KEY=your_anthropic_api_key_here" .env; then
        echo -e "${YELLOW}! WARNING:${NC} ANTHROPIC_API_KEY is not configured"
        echo "  Please edit .env and add your API key"
    else
        echo -e "${GREEN}✓${NC} ANTHROPIC_API_KEY appears to be configured"
    fi
fi

# Create necessary directories
print_header "Creating Directories"

mkdir -p backend/app/workspaces
mkdir -p logs
mkdir -p docs

echo -e "${GREEN}✓${NC} Directories created"

# Validate project structure
print_header "Validating Project Structure"

STRUCTURE_OK=true

# Check critical files
critical_files=(
    "backend/app/main.py"
    "backend/app/config.py"
    "backend/app/core/engine.py"
    "backend/requirements.txt"
    "frontend/package.json"
    "frontend/src/main.tsx"
    "docker-compose.yml"
)

for file in "${critical_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file MISSING"
        STRUCTURE_OK=false
    fi
done

if [ "$STRUCTURE_OK" = false ]; then
    echo -e "\n${RED}ERROR: Project structure is incomplete!${NC}"
    exit 1
fi

# Check Docker
print_header "Docker Status"

if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    echo -e "${RED}✗${NC} Docker daemon is not running"
    echo "Please start Docker and try again."
    exit 1
fi

# Offer to build images
print_header "Docker Images"

read -p "Would you like to build Docker images now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Building images (this may take a few minutes)..."
    docker-compose build
    echo -e "${GREEN}✓${NC} Docker images built successfully"
fi

# Print summary
print_header "Setup Summary"

echo -e "${GREEN}✓${NC} All checks passed!"
echo ""
echo "Your Project Core installation is ready."
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "1. Ensure your ANTHROPIC_API_KEY is set in .env"
echo "2. Start the services:"
echo -e "   ${GREEN}docker-compose up -d${NC}"
echo ""
echo "3. Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "4. View logs:"
echo -e "   ${GREEN}docker-compose logs -f${NC}"
echo ""
echo "5. Stop services:"
echo -e "   ${GREEN}docker-compose down${NC}"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  - Quick Start: docs/QUICKSTART.md"
echo "  - Deployment:  docs/DEPLOYMENT.md"
echo "  - Structure:   PROJECT_STRUCTURE.md"
echo ""
echo -e "${GREEN}Happy building! 🚀${NC}"
