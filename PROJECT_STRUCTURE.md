# Project Core - Complete Structure

## Directory Tree

```
project-core/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   └── routes.py      # Main API routes
│   │   ├── core/              # Core engine (PEVR loop)
│   │   │   └── engine.py      # Main orchestration engine
│   │   ├── models/            # Database models
│   │   │   └── database.py    # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── requests.py    # Request models
│   │   │   └── responses.py   # Response models
│   │   ├── services/          # Business logic services
│   │   │   ├── llm_service.py # Anthropic Claude integration
│   │   │   ├── diff_engine.py # Safe code modification
│   │   │   ├── planner.py     # Plan creation
│   │   │   ├── executor.py    # Plan execution
│   │   │   ├── verifier.py    # Test running & verification
│   │   │   └── reflector.py   # Learning from results
│   │   ├── utils/             # Utilities
│   │   │   ├── exceptions.py  # Custom exceptions
│   │   │   ├── code_analyzer.py # Code analysis
│   │   │   └── token_counter.py # Token counting
│   │   ├── config.py          # Configuration management
│   │   └── main.py            # FastAPI application
│   ├── tests/                 # Tests
│   │   ├── unit/             # Unit tests
│   │   └── integration/      # Integration tests
│   ├── migrations/            # Alembic migrations
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile            # Backend Docker image
│   ├── pytest.ini            # Pytest configuration
│   └── conftest.py           # Test fixtures
│
├── frontend/                  # React TypeScript frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Page components
│   │   │   ├── Home.tsx      # Home page
│   │   │   └── ProjectView.tsx # Project view
│   │   ├── services/         # API services
│   │   ├── hooks/            # Custom React hooks
│   │   ├── utils/            # Utilities
│   │   ├── types/            # TypeScript types
│   │   ├── App.tsx           # Main App component
│   │   ├── main.tsx          # Entry point
│   │   └── index.css         # Global styles
│   ├── public/               # Static assets
│   ├── package.json          # NPM dependencies
│   ├── tsconfig.json         # TypeScript config
│   ├── vite.config.ts        # Vite config
│   ├── tailwind.config.js    # Tailwind CSS config
│   └── Dockerfile            # Frontend Docker image
│
├── docs/                      # Documentation
│   ├── QUICKSTART.md         # Quick start guide
│   ├── DEPLOYMENT.md         # Deployment guide
│   ├── architecture.md       # Architecture details
│   ├── api-reference.md      # API documentation
│   └── security.md           # Security information
│
├── scripts/                   # Utility scripts
│   ├── setup.sh              # Initial setup
│   ├── dev.sh                # Development environment
│   └── test.sh               # Run tests
│
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── docker-compose.yml        # Docker Compose config
├── README.md                 # Project README
├── CONTRIBUTING.md           # Contribution guidelines
└── LICENSE                   # MIT License
```

## Key Components

### Backend Architecture

1. **Core Engine** (`app/core/engine.py`)
   - Orchestrates Plan → Execute → Verify → Reflect loop
   - Manages action lifecycle
   - Handles approval workflows

2. **Services**
   - **LLM Service**: Controlled interface to Claude API
   - **Diff Engine**: Safe, reversible code modifications
   - **Planner**: Converts intent to execution plans
   - **Executor**: Generates and applies code changes
   - **Verifier**: Runs tests and validates changes
   - **Reflector**: Learns from execution results

3. **Database Models**
   - Users, Projects, Sessions
   - Actions (PEVR cycles)
   - Diffs (code changes)
   - Audit Logs

### Frontend Architecture

1. **Pages**
   - Home: Project listing
   - ProjectView: Code editor and execution interface

2. **State Management**
   - React Query for server state
   - Zustand for client state

3. **Editor**
   - Monaco Editor for code viewing
   - Diff viewer for reviewing changes

## Technology Stack

### Backend
- **Framework**: FastAPI (async Python)
- **Database**: PostgreSQL
- **Cache**: Redis
- **LLM**: Anthropic Claude (Sonnet 4)
- **Testing**: Pytest

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State**: React Query + Zustand
- **Editor**: Monaco Editor

### DevOps
- **Containerization**: Docker + Docker Compose
- **CI/CD**: GitHub Actions (ready to add)
- **Monitoring**: Sentry, Prometheus

## Core Principles

1. **Safety First**
   - All changes via diffs
   - Automatic rollback on failure
   - Approval gates for risky operations

2. **LLM as Component**
   - LLM output is never trusted blindly
   - Tools provide ground truth
   - Verification is mandatory

3. **Engineering Process**
   - Every action follows PEVR loop
   - No silent changes
   - Full audit trail

4. **Security by Default**
   - Execution requires permission
   - Sandboxed environments
   - No secret exposure

## Getting Started

1. **Setup**: `./scripts/setup.sh`
2. **Configure**: Edit `.env` with API keys
3. **Start**: `docker-compose up -d`
4. **Access**: http://localhost:3000

## Development

- **Local Dev**: `./scripts/dev.sh`
- **Run Tests**: `./scripts/test.sh`
- **View Logs**: `docker-compose logs -f`

## Production Deployment

See `docs/DEPLOYMENT.md` for detailed instructions on deploying to production environments.
