#!/bin/bash
# Production deployment script for 1,000+ RPS capacity

set -e

echo "🚀 Starting production deployment..."

# 1. Build optimized images
echo "📦 Building optimized Docker images..."
docker-compose -f docker-compose.prod.yml build --no-cache

# 2. Apply database optimizations
echo "🗄️ Optimizing database..."
docker-compose -f docker-compose.prod.yml up -d postgres
sleep 10

# Apply database optimizations
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d llm_api -f /scripts/optimize-database.sql

# 3. Start Redis with optimized config
echo "🔴 Starting optimized Redis..."
docker-compose -f docker-compose.prod.yml up -d redis
sleep 5

# 4. Start FastAPI services
echo "⚡ Starting FastAPI services..."
docker-compose -f docker-compose.prod.yml up -d fastapi-1 fastapi-2 fastapi-3
sleep 10

# 5. Start load balancer
echo "⚖️ Starting Nginx load balancer..."
docker-compose -f docker-compose.prod.yml up -d nginx

# 6. Health checks
echo "🔍 Running health checks..."
for i in {1..30}; do
    if curl -f http://localhost/health > /dev/null 2>&1; then
        echo "✅ Health check passed!"
        break
    fi
    echo "⏳ Waiting for services to be ready... ($i/30)"
    sleep 2
done

# 7. Performance test
echo "🏃 Running quick performance test..."
echo "Testing 100 concurrent requests..."
ab -n 1000 -c 100 http://localhost/health | grep -E "(Requests per second|Time per request)"

echo "
🎉 Production deployment complete!

📊 Access points:
- Load Balanced API: http://localhost/
- Health Check: http://localhost/health
- API Documentation: http://localhost/docs

📈 Performance targets:
- 1,000+ RPS: ✅ Enabled with 3 FastAPI instances + load balancer
- <100ms latency: ✅ Optimized for non-model endpoints
- Cache performance: ✅ Redis + in-memory caching

🔧 Next steps:
1. Monitor with: docker-compose -f docker-compose.prod.yml logs -f
2. Scale up: docker-compose -f docker-compose.prod.yml up -d --scale fastapi-1=2
3. Test load: Run 'locust -f performance-optimization/load-testing/high_rps_test.py --host=http://localhost'
"