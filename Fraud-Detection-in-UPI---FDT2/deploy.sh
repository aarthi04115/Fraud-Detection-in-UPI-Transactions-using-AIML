#!/bin/bash
#
# FDT Secure - Quick Deploy Script for Docker Compose
# Usage: bash deploy.sh [start|stop|restart|status|logs]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Install from: https://get.docker.com"
        exit 1
    fi
    print_success "Docker installed ($(docker --version))"
    
    # Check docker compose (plugin)
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        echo "Install from: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose installed ($(docker compose version))"
    
    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "docker-compose.yml not found at $COMPOSE_FILE"
        exit 1
    fi
    print_success "docker-compose.yml found"
    
    # Check if .env exists
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_warning ".env file not found - some services may not work correctly"
        print_warning "Creating .env from template..."
        cat > "$PROJECT_DIR/.env" << 'ENVEOF'
# FDT Secure Environment Variables
DB_URL=postgresql://fdt:fdtpass@db:5432/fdt_db
DELAY_THRESHOLD=0.35
BLOCK_THRESHOLD=0.70
GROQ_API_KEY=
JWT_SECRET_KEY=change_in_production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ENVEOF
        print_success ".env created (please update with your values)"
    fi
    
    echo
}

# Start services
start_services() {
    print_header "Starting FDT Secure Services"
    
    cd "$PROJECT_DIR"
    
    # Validate docker-compose
    echo "Validating docker-compose.yml..."
    if ! docker compose config > /dev/null 2>&1; then
        print_error "Invalid docker-compose.yml"
        docker compose config
        exit 1
    fi
    print_success "Configuration valid"
    
    # Start services
    echo "Starting containers..."
    docker compose up -d
    
    # Wait for services
    echo "Waiting for services to be healthy..."
    sleep 5
    
    # Check status
    docker compose ps
    
    print_success "Services started!"
    echo
    echo "Next steps:"
    echo "  • Check logs: docker compose logs -f"
    echo "  • API docs: http://localhost:8001/docs"
    echo "  • Admin: http://localhost:8000"
    echo
}

# Stop services
stop_services() {
    print_header "Stopping FDT Secure Services"
    
    cd "$PROJECT_DIR"
    
    echo "Stopping containers..."
    docker compose stop
    
    print_success "Services stopped"
    echo
}

# Restart services
restart_services() {
    print_header "Restarting FDT Secure Services"
    
    cd "$PROJECT_DIR"
    
    echo "Restarting containers..."
    docker compose restart
    
    sleep 3
    
    # Check status
    docker compose ps
    
    print_success "Services restarted"
    echo
}

# Show status
show_status() {
    print_header "FDT Secure Service Status"
    
    cd "$PROJECT_DIR"
    
    if ! docker compose ps > /dev/null 2>&1; then
        print_error "No services running"
        exit 1
    fi
    
    docker compose ps
    
    echo
    echo "Service Health:"
    
    # Check database
    if docker compose exec -T db pg_isready -U fdt > /dev/null 2>&1; then
        print_success "PostgreSQL: Healthy"
    else
        print_error "PostgreSQL: Unhealthy"
    fi
    
    # Check redis
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        print_success "Redis: Healthy"
    else
        print_error "Redis: Unhealthy"
    fi
    
    echo
}

# Show logs
show_logs() {
    print_header "FDT Secure Logs"
    
    cd "$PROJECT_DIR"
    
    # Check which service to follow
    if [ -z "$2" ]; then
        echo "Following all services (Ctrl+C to stop)..."
        docker compose logs -f
    else
        echo "Following $2 service..."
        docker compose logs -f "$2"
    fi
}

# Verify deployment
verify_deployment() {
    print_header "Verifying Deployment"
    
    cd "$PROJECT_DIR"
    
    echo "Checking services..."
    
    # Get service status
    services=$(docker compose ps --services --filter "status=running")
    
    expected_services=("db" "redis")
    
    for service in "${expected_services[@]}"; do
        if echo "$services" | grep -q "^${service}$"; then
            print_success "$service is running"
        else
            print_error "$service is not running"
        fi
    done
    
    echo
    echo "Connection Tests:"
    
    # Test database
    if docker compose exec -T db psql -U fdt -d fdt_db -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "PostgreSQL connection successful"
    else
        print_error "PostgreSQL connection failed"
    fi
    
    # Test redis
    if docker compose exec -T redis redis-cli ping | grep -q "PONG"; then
        print_success "Redis connection successful"
    else
        print_error "Redis connection failed"
    fi
    
    echo
    print_success "Deployment verified!"
    echo
}

# Show help
show_help() {
    cat << 'HELPEOF'
FDT Secure - Docker Compose Deployment Script

Usage: bash deploy.sh [COMMAND]

Commands:
  start           Start all services
  stop            Stop all services
  restart         Restart all services
  status          Show service status
  logs [SERVICE]  Show logs (optionally for specific service)
  verify          Verify deployment health
  help            Show this help message

Examples:
  bash deploy.sh start              # Start all services
  bash deploy.sh stop               # Stop all services
  bash deploy.sh logs db            # Show PostgreSQL logs
  bash deploy.sh status             # Check service status
  bash deploy.sh verify             # Verify deployment

Service Names:
  • db            PostgreSQL database
  • redis         Redis cache

HELPEOF
}

# Main logic
main() {
    command="${1:-start}"
    
    case "$command" in
        start)
            check_prerequisites
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$@"
            ;;
        verify)
            verify_deployment
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

main "$@"
