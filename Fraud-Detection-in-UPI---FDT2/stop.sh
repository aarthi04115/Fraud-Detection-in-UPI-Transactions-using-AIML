#!/bin/bash
# Stop script for FDT application

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping FDT Application...${NC}"
echo ""

# Kill backend processes
echo "Stopping backend servers..."
pkill -f "python backend/server.py" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Kill frontend processes
echo "Stopping frontend server..."
pkill -9 -f "react-scripts/scripts/start.js" 2>/dev/null || true
pkill -f "npm start" 2>/dev/null || true
pkill -f "node.*react-scripts" 2>/dev/null || true
# Also kill by port to ensure clean shutdown
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Stop Docker services
echo "Stopping Docker services..."
docker compose down

echo ""
echo -e "${GREEN}✓ All services stopped${NC}"
