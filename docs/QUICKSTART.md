# Quick Start Guide

## Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.11+ and Node.js 18+ for local development

## Getting Started

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd project-core

# Copy environment template
cp .env.example .env

# Edit .env file with your settings
# REQUIRED: Add your Anthropic API key
nano .env
```

### 2. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4. Run Locally (Optional)

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## First Steps

1. Create a new project
2. Describe what you want to build
3. Review the generated plan
4. Approve and let the system execute
5. Tests run automatically
6. Review diffs before they're applied

## Next Steps

- Read the [Architecture Guide](architecture.md)
- Explore the [API Reference](api-reference.md)
- Learn about [Security](security.md)
