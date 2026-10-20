# AI Kubernetes Agent

AI-powered Kubernetes troubleshooting agent that investigates cluster issues, performs root-cause analysis using LLM reasoning, and provides actionable fix suggestions.

## Architecture

```
Frontend (Next.js)
    ↓
FastAPI Backend (Orchestrator)
    ↓
Kubernetes Investigation Layer
    ↓
AI Reasoning (OpenRouter LLM)
    ↓
Root Cause + Suggested Fix
    ↓
Frontend Diagnosis
```

## Tech Stack

| Layer          | Technology                            |
| -------------- | ------------------------------------- |
| Frontend       | Next.js, TypeScript, Tailwind CSS     |
| Backend        | FastAPI, Python 3.12+, Uvicorn        |
| AI             | OpenRouter (LLM)                      |
| Infrastructure | Docker, Docker Compose                |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose

### 1. Clone & configure

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` with your API keys when ready.

### 2. Run

```bash
docker compose up --build
```

### 3. Verify

| Service  | URL                          |
| -------- | ---------------------------- |
| Frontend | http://localhost:3000         |
| Backend  | http://localhost:8000/health  |

## Project Structure

```
ai-kubernetes-agent/
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP endpoints
│   │   ├── core/         # Config, logging
│   │   ├── kubernetes/   # Cluster inspection
│   │   ├── ai/           # LLM reasoning
│   │   ├── services/     # Orchestration
│   │   └── models/       # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   ├── services/     # API client
│   │   ├── hooks/        # React hooks
│   │   └── types/        # TypeScript types
│   ├── Dockerfile
│   └── package.json
├── docs/
├── prompts/
├── docker-compose.yml
└── README.md
```

## License

MIT
