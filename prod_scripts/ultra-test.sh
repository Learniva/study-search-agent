#!/bin/bash

echo "Ultra-minimal setup test..."

echo "Starting core services..."
docker compose -f docker-compose.dev.yml up -d postgres redis

echo "Waiting for services..."
sleep 5

echo "Building ultra-minimal image..."
docker build -f Dockerfile.minimal -t study-search-agent:ultra-minimal .

if [ $? -eq 0 ]; then
    echo "Build successful!"
    
    echo "Testing application..."
    docker run --rm -d \
        --name ultra-test \
        --network study-search-agent_app-network \
        -p 8001:8000 \
        -e DATABASE_URL="postgresql://postgres:postgres@postgres:5432/study_search_agent" \
        -e REDIS_URL="redis://redis:6379/0" \
        -e GOOGLE_API_KEY="test-key" \
        study-search-agent:ultra-minimal
    
    sleep 15
    
    echo "Checking application status..."
    if curl -f http://localhost:8001/health 2>/dev/null; then
        echo "Application is healthy!"
    else
        echo "Health check failed, showing logs:"
        docker logs ultra-test --tail 20
    fi
    
    echo "Testing basic API endpoint..."
    if curl -f http://localhost:8001/docs 2>/dev/null; then
        echo "API docs accessible!"
    else
        echo "API docs not accessible"
    fi
    
    docker stop ultra-test
    echo "Test complete!"
else
    echo "Build failed"
    exit 1
fi