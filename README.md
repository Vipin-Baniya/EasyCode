# Project Core

**A secure, engineering-grade LLM software system that transforms ideas into production-ready software**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)

## 🎯 What is Project Core?

Project Core enables anyone—from non-coders to advanced developers—to build heavy, real-world software safely and verifiably. It's an LLM-powered system that treats code generation as an engineering process, not a conversation.

### Key Principles

- **Safety First**: Diff-based changes, automatic rollback, no silent modifications
- **Verification Over Confidence**: Tests and execution results are the source of truth
- **Engineering Process**: Plan → Execute → Verify → Reflect loop for every action
- **LLM as Component**: The LLM is supervised, not authoritative

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd project-core

# Copy environment template
cp .env.example .env

# Edit .env with your settings (API keys, etc.)
nano .env

# Start with Docker Compose
docker-compose up -d

# Or run locally:
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Access the application at `http://localhost:3000`

## 📋 Features

### Core Capabilities

- ✅ **Idea to Product**: Transform vague ideas into working software
- ✅ **Heavy Coding**: Multi-file refactors, deep bug fixes, feature additions
- ✅ **Verification**: Automatic test running (pytest, npm test)
- ✅ **Safe Iteration**: Diff preview, approval gates, automatic rollback
- ✅ **Multi-Language**: Python, JavaScript/TypeScript, and more

### Security Features

- 🔒 Execution permissions system
- 🔒 Sandboxed code execution
- 🔒 No secret exposure
- 🔒 Full audit trail
- 🔒 Human-in-the-loop for destructive actions

## 🏗️ Architecture

```
project-core/
├── backend/           # FastAPI backend service
│   ├── app/
│   │   ├── core/     # Core engine (planner, executor, verifier)
│   │   ├── services/ # LLM, code analysis, diff engine
│   │   ├── api/      # REST API endpoints
│   │   └── models/   # Database models
├── frontend/         # React/TypeScript IDE
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── pages/
├── shared/           # Shared types and utilities
├── docker/           # Docker configurations
└── docs/             # Documentation
```

## 🔄 How It Works

### The Core Loop

Every coding action follows this cycle:

1. **Plan**: Understand intent, decompose into steps, identify risks
2. **Execute**: Make minimal, explicit changes via diffs
3. **Verify**: Run tests, execute code, gather evidence
4. **Reflect**: Learn from results, revise plans, proceed safely

### Example Workflow

```
User: "Build me a REST API for a task management system"

System:
├─ Plan: Design data models, API structure, testing strategy
├─ Execute: Generate files with diffs
├─ Verify: Run pytest, check for errors
└─ Reflect: Adjust based on test results
```

## 📚 Documentation

- [Architecture Guide](docs/architecture.md)
- [API Reference](docs/api-reference.md)
- [Security Model](docs/security.md)
- [Development Guide](docs/development.md)
- [Deployment Guide](docs/deployment.md)

## 🛠️ Technology Stack

### Backend
- **FastAPI**: High-performance async API framework
- **SQLAlchemy**: Database ORM
- **PostgreSQL**: Primary database
- **Redis**: Caching and task queue
- **Anthropic Claude**: LLM reasoning engine

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **TailwindCSS**: Styling
- **React Query**: Data fetching
- **Monaco Editor**: Code editor

### DevOps
- **Docker**: Containerization
- **Docker Compose**: Local orchestration
- **GitHub Actions**: CI/CD
- **Pytest**: Backend testing
- **Vitest**: Frontend testing

## 🔐 Security

Project Core is built with security as a first-class concern:

- All code execution requires explicit permission
- Sandboxed execution environments
- No automatic destructive actions
- Complete audit logging
- Secret management via environment variables
- Rate limiting and request validation

See [Security Documentation](docs/security.md) for details.

## 📊 Use Cases

### For Non-Coders
- Turn ideas into working products
- No coding knowledge required
- Safe, guided software creation

### For Founders
- Rapid prototyping
- MVP development
- CTO-like technical assistance

### For Developers
- Heavy refactoring tasks
- Multi-repo operations
- Time-consuming implementations

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built on the philosophy that software creation should be accessible, safe, and reliable for everyone.

## 📞 Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues
- Discussions: GitHub Discussions

---

**Built for years, not demos. For real products, not snippets. For trust, not hype.**
