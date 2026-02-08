#!/bin/bash
# Start only the admin dashboard (app/main.py)
# Assumes Docker services are already running

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FDT Admin Dashboard Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Initialize conda
echo "Activating conda environment 'dev'..."
eval "$(conda shell.bash hook)"
conda activate dev
echo -e "${GREEN}✓${NC} Conda environment 'dev' activated"
echo ""

# Start admin dashboard
echo -e "${YELLOW}Starting admin dashboard on port 8000...${NC}"
echo ""
echo -e "${GREEN}Access at: http://localhost:8000${NC}"
echo -e "${GREEN}API Docs: http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
