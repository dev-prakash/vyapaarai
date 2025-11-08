# VyaparAI Monorepo

A comprehensive AI-powered business assistant platform with backend API, frontend PWA, and browser extension.

## Project Structure

```
vyaparai/
├── backend/           # FastAPI backend with AI integration
├── ai-agent/          # AI agent components
├── frontend-pwa/      # React PWA frontend
├── extension/         # Browser extension
├── shared/            # Shared utilities and types
├── deployment/        # Deployment configurations
│   ├── k8s/          # Kubernetes manifests
│   └── docker/       # Docker configurations
└── setup.sh          # Setup script
```

## Quick Start

1. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start database services:**
   ```bash
   docker-compose up -d
   ```

4. **Start development servers:**
   ```bash
   # Backend
   cd backend
   poetry run uvicorn main:app --reload

   # Frontend (in another terminal)
   cd frontend-pwa
   yarn dev

   # Extension (in another terminal)
   cd extension
   yarn dev
   ```

## Environment Variables

Copy `.env.example` to `.env` and configure your API keys:

- `GOOGLE_API_KEY`: Google AI API key
- `GOOGLE_GENERATIVE_AI_API_KEY`: Google Generative AI API key
- `VERTEX_PROJECT_ID`: Google Vertex AI project ID
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string

## Development

- **Backend**: FastAPI with Poetry dependency management
- **AI Agent**: LangChain and LangGraph integration
- **Frontend**: React 18 with TypeScript, Vite, and Tailwind CSS
- **Extension**: Chrome extension with Manifest V3
- **Database**: PostgreSQL 16 and Redis 7.4

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
