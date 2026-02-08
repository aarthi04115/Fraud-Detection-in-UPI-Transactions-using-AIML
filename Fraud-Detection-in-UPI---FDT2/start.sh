#!/bin/bash
# Start script for FDT application using Docker and Conda
# Uses conda 'dev' environment and Docker for PostgreSQL/Redis
#
# Usage:
#   ./start.sh          - Start user backend + frontend
#   ./start.sh --admin  - Start user backend + admin dashboard + frontend

set -e

# Parse arguments
START_ADMIN=false
if [ "$1" == "--admin" ]; then
    START_ADMIN=true
fi

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FDT Application Startup (Docker + Conda)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if conda env exists
check_conda_env() {
    if conda env list | grep -q "^dev "; then
        echo -e "${GREEN}✓${NC} Conda environment 'dev' found"
        return 0
    else
        echo -e "${RED}✗${NC} Conda environment 'dev' not found"
        echo "  Create it with: conda create -n dev python=3.11"
        return 1
    fi
}

# Function to check if Docker is running
check_docker() {
    if docker info &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker is running"
        return 0
    else
        echo -e "${RED}✗${NC} Docker is not running"
        echo "  Start Docker service first"
        return 1
    fi
}

# Check prerequisites
echo "Checking prerequisites..."
check_docker || exit 1
check_conda_env || exit 1
echo ""

# Start Docker services
echo -e "${YELLOW}Starting Docker services (PostgreSQL & Redis)...${NC}"
docker compose up -d

# Wait for services to be healthy
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if docker compose exec -T db pg_isready -U fdt &> /dev/null; then
        echo -e "${GREEN}✓${NC} PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗${NC} PostgreSQL failed to start"
        exit 1
    fi
    sleep 1
done

echo "Waiting for Redis to be ready..."
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓${NC} Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠${NC} Redis not responding (optional)"
        break
    fi
    sleep 1
done
echo ""

# Initialize conda
echo "Activating conda environment 'dev'..."
eval "$(conda shell.bash hook)"
conda activate dev
echo -e "${GREEN}✓${NC} Conda environment 'dev' activated"
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."
if python -c "import fastapi, psycopg2, redis, sklearn, xgboost" &> /dev/null; then
    echo -e "${GREEN}✓${NC} All Python dependencies installed"
else
    echo -e "${YELLOW}⚠${NC} Missing Python dependencies. Installing..."
    pip install -r requirements.txt
fi
echo ""

# Create frontend .env if missing
if [ ! -f "frontend/.env" ]; then
    echo "Creating frontend/.env..."
    echo "REACT_APP_BACKEND_URL=http://localhost:8001" > frontend/.env
    echo -e "${GREEN}✓${NC} Created frontend/.env"
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓${NC} Frontend dependencies installed"
fi
echo ""

# Display status
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Services are ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Docker Services:${NC}"
echo "  PostgreSQL: localhost:5433"
echo "  Redis: localhost:6379"
echo ""
echo -e "${BLUE}Starting Application Servers:${NC}"
echo ""

# Check if ports are already in use
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} Port 8001 already in use. Stopping existing process..."
    pkill -9 -f "backend/server.py" 2>/dev/null || true
    sleep 2
fi

# Start user backend in background
echo -e "${YELLOW}Starting user backend server (port 8001)...${NC}"
python backend/server.py > /tmp/fdt-backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓${NC} User backend started (PID: $BACKEND_PID)"
echo "  Logs: /tmp/fdt-backend.log"
echo ""

# Start admin dashboard if requested
ADMIN_PID=""
if [ "$START_ADMIN" = true ]; then
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}✗${NC} Port 8000 already in use. Stopping existing process..."
        pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
        sleep 2
    fi
    
    echo -e "${YELLOW}Starting admin dashboard (port 8000)...${NC}"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/fdt-admin.log 2>&1 &
    ADMIN_PID=$!
    echo -e "${GREEN}✓${NC} Admin dashboard started (PID: $ADMIN_PID)"
    echo "  Logs: /tmp/fdt-admin.log"
    echo ""
fi

# Wait a bit for backend to start
sleep 3

# Check if frontend port is already in use
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} Port 3000 already in use. Stopping existing process..."
    # Kill react-scripts process specifically
    pkill -9 -f "react-scripts/scripts/start.js" 2>/dev/null || true
    # Also try killing by port
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Start frontend in background
echo -e "${YELLOW}Starting frontend server (port 3000)...${NC}"
cd frontend
npm start &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Application is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo "  Frontend: http://localhost:3000"
echo "  User API: http://localhost:8001"
echo "  API Docs: http://localhost:8001/docs"
if [ "$START_ADMIN" = true ]; then
    echo "  Admin Dashboard: http://localhost:8000"
    echo "  Admin Docs: http://localhost:8000/docs"
fi
echo ""
echo -e "${BLUE}Demo Login:${NC}"
echo "  Phone: +919876543210"
echo "  Password: password123"
echo ""
if [ "$START_ADMIN" = false ]; then
    echo -e "${YELLOW}Tip: Run './start.sh --admin' to start admin dashboard too${NC}"
    echo ""
fi
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    if [ -n "$ADMIN_PID" ]; then
        kill $ADMIN_PID 2>/dev/null || true
    fi
    docker compose down
    echo -e "${GREEN}✓${NC} All services stopped"
    exit 0
}

# Trap Ctrl+C and cleanup
trap cleanup INT TERM

# Wait for user interrupt
wait
