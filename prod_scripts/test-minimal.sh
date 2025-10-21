#!/bin/bash

echo "Minimal development setup test..."

# Stop any existing containers
echo "Stopping existing containers..."
docker compose -f docker-compose.dev.yml down

echo "Starting core services (PostgreSQL + Redis)..."
docker compose -f docker-compose.dev.yml up -d postgres redis

echo " Waiting for services to be ready..."
sleep 10

# Check if services are ready
if docker compose -f docker-compose.dev.yml exec postgres pg_isready -q; then
    echo "PostgreSQL... ✓ Ready"
else
    echo "PostgreSQL... ✗ Not ready"
    exit 1
fi

if docker compose -f docker-compose.dev.yml exec redis redis-cli ping | grep -q PONG; then
    echo "Redis... ✓ Ready"
else
    echo "Redis... ✗ Not ready"
    exit 1
fi

echo ""
echo " Core services are ready!"

echo ""
echo "🔨 Building minimal application image..."
docker build -f Dockerfile.minimal -t study-search-agent:minimal .

if [ $? -eq 0 ]; then
    echo " Minimal build successful!"
    echo ""
    echo " Starting minimal application..."
    
    # Test the minimal application
    docker run --rm -d \
        --name study-search-test \
        --network study-search-agent_app-network \
        -p 8000:8000 \
        -e DATABASE_URL="postgresql://postgres:postgres@postgres:5432/study_search_agent" \
        -e REDIS_URL="redis://redis:6379/0" \
        study-search-agent:minimal
    
    # Wait for app to start
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:8000/health 2>/dev/null; then
        echo " Application is running and healthy!"
        echo " API available at: http://localhost:8000"
        echo " API docs available at: http://localhost:8000/docs"
    else
        echo "  Application started but health check failed"
    fi
    
    # Show logs
    echo ""
    echo " Application logs:"
    docker logs study-search-test --tail 10
    
    # Clean up
    docker stop study-search-test
    
else
    echo " Minimal build failed"
    exit 1
fi