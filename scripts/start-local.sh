#!/bin/bash

echo "🚀 Starting VyaparAI Local Development Environment"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start backend services
echo "📦 Starting backend services (PostgreSQL, Redis)..."
docker-compose -f docker-compose.dev.yml up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Run database migrations (if any)
echo "🔄 Setting up database..."
docker-compose -f docker-compose.dev.yml exec -T postgres psql -U vyaparai -d vyaparai_dev < backend/scripts/init-db.sql 2>/dev/null || true

# Install backend dependencies
echo "📚 Installing backend dependencies..."
cd backend
pip install -r requirements.txt > /dev/null 2>&1

# Start backend server
echo "🖥️  Starting backend server..."
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Install frontend dependencies
echo "📱 Installing frontend dependencies..."
cd frontend-pwa
npm install > /dev/null 2>&1

# Start frontend dev server
echo "🎨 Starting frontend server..."
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for servers to start
sleep 5

echo "✅ All services started successfully!"
echo ""
echo "📍 Access points:"
echo "   Frontend PWA: http://localhost:3000"
echo "   Backend API:  http://localhost:8000"
echo "   API Docs:     http://localhost:8000/docs"
echo "   Test Panel:   http://localhost:3000/test"
echo ""
echo "📝 To stop all services, press Ctrl+C"

# Wait for interrupt
trap "echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID; docker-compose -f docker-compose.dev.yml down; exit" INT
wait
