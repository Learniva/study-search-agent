#!/bin/bash

# Test script for containerized Study Search Agent
# This script tests the application after docker-compose up

set -e

echo "Testing Study Search Agent Container Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if service is running
check_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1

    echo -n "Checking $service on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓ Ready${NC}"
            return 0
        fi
        
        if [ $attempt -eq 1 ]; then
            echo -n " waiting"
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e " ${RED}✗ Failed${NC}"
    return 1
}

# Function to test API endpoint
test_api_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -n "Testing $description..."
    
    if curl -s -f "http://localhost:8000$endpoint" > /dev/null; then
        echo -e " ${GREEN}✓ Pass${NC}"
    else
        echo -e " ${RED}✗ Fail${NC}"
        return 1
    fi
}

# Function to test query endpoint
test_query() {
    local query="$1"
    local role="$2"
    
    echo -n "Testing query: '$query'..."
    
    response=$(curl -s -X POST "http://localhost:8000/query/" \
        -H "Content-Type: application/json" \
        -H "X-User-Role: $role" \
        -d "{\"question\": \"$query\", \"user_role\": \"$role\"}")
    
    if echo "$response" | grep -q "answer"; then
        echo -e " ${GREEN}✓ Pass${NC}"
    else
        echo -e " ${RED}✗ Fail${NC}"
        echo "Response: $response"
        return 1
    fi
}

echo "Pre-flight checks..."

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker Desktop${NC}"
    exit 1
fi

# Check if containers are running
if ! docker compose ps | grep -q "Up" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Containers not running. Starting them...${NC}"
    docker compose up -d
    sleep 15
fi

echo ""
echo " Service Health Checks..."

# Check application health
check_service "Study Search Agent" 8000 || exit 1

# Check PostgreSQL
if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "PostgreSQL... ${GREEN}✓ Ready${NC}"
else
    echo -e "PostgreSQL... ${RED}✗ Failed${NC}"
    exit 1
fi

# Check Redis
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "Redis... ${GREEN}✓ Ready${NC}"
else
    echo -e "Redis... ${RED}✗ Failed${NC}"
    exit 1
fi

echo ""
echo " API Endpoint Tests..."

# Test basic endpoints
test_api_endpoint "/" "Root endpoint" || exit 1
test_api_endpoint "/health" "Health check" || exit 1
test_api_endpoint "/docs" "API documentation" || exit 1

# Test database health (if available)
test_api_endpoint "/health/database" "Database health" || echo -e "${YELLOW}⚠ Database health check not available${NC}"

echo ""
echo " Agent Functionality Tests..."

# Test simple query (only if GOOGLE_API_KEY is set)
if [ -n "$GOOGLE_API_KEY" ]; then
    test_query "What is 2+2?" "student" || echo -e "${YELLOW}⚠ Query test failed (API key issue?)${NC}"
else
    echo -e "${YELLOW}⚠ Skipping query tests (GOOGLE_API_KEY not set)${NC}"
fi

echo ""
echo " Container Resource Usage..."

# Show resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -10

echo ""
echo " Log Sample..."

# Show recent logs
echo "Recent application logs:"
docker compose logs --tail=10 app

echo ""
echo -e "${GREEN} Container tests completed!${NC}"

echo ""
echo " Access URLs:"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/health"
echo "  • Prometheus (if enabled): http://localhost:9090"
echo "  • Grafana (if enabled): http://localhost:3000"

echo ""
echo " Useful commands:"
echo "  • View logs: docker compose logs -f app"
echo "  • Scale up: docker compose up --scale app=3"  
echo "  • Stop: docker compose down"
echo "  • Restart: docker compose restart app"