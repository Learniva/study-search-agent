#!/bin/bash

# Quick test script for development setup
# Tests core services without building the full application

set -e

echo "Starting development environment test..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Starting core services (PostgreSQL + Redis)..."

# Start just the database services first
docker compose -f docker-compose.dev.yml up -d postgres redis

echo "Waiting for services to initialize..."
sleep 10

# Check PostgreSQL
if docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "PostgreSQL... ${GREEN}Ready${NC}"
else
    echo -e "PostgreSQL... ${RED}Failed${NC}"
    echo "Checking logs:"
    docker compose -f docker-compose.dev.yml logs postgres
    exit 1
fi

# Check Redis
if docker compose -f docker-compose.dev.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "Redis... ${GREEN}✓ Ready${NC}"
else
    echo -e "Redis... ${RED}✗ Failed${NC}"
    echo "Checking logs:"
    docker compose -f docker-compose.dev.yml logs redis
    exit 1
fi

echo ""
echo -e "${GREEN} Core services are ready!${NC}"

echo ""
echo " Now starting the application..."
docker compose -f docker-compose.dev.yml up -d app

echo " Waiting for application to start..."
sleep 30

# Test application health
echo -n "Testing application health..."
max_attempts=20
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
        echo -e " ${GREEN}✓ Ready${NC}"
        break
    fi
    
    if [ $attempt -eq $max_attempts ]; then
        echo -e " ${RED}✗ Failed${NC}"
        echo "Application logs:"
        docker compose -f docker-compose.dev.yml logs app
        exit 1
    fi
    
    echo -n "."
    sleep 3
    attempt=$((attempt + 1))
done

echo ""
echo -e "${GREEN} Development setup complete!${NC}"

echo ""
echo " Access URLs:"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/health"

echo ""
echo " Useful commands:"
echo "  • View logs: docker compose -f docker-compose.dev.yml logs -f app"
echo "  • Stop: docker compose -f docker-compose.dev.yml down"
echo "  • Restart app: docker compose -f docker-compose.dev.yml restart app"

echo ""
echo " Quick API test:"
if [ -n "$GOOGLE_API_KEY" ]; then
    echo "Testing simple query..."
    curl -s -X POST "http://localhost:8000/query/" \
        -H "Content-Type: application/json" \
        -H "X-User-Role: student" \
        -d '{"question": "What is 2+2?", "user_role": "student"}' \
        | head -200
    echo ""
else
    echo "Set GOOGLE_API_KEY in your .env file to test queries"
fi