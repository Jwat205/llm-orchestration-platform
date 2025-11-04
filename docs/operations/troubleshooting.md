# Troubleshooting Guide

This guide covers common issues, diagnostic procedures, and resolution steps for the LLM API Platform.

## Quick Diagnostics

### Health Check Commands

```bash
# Check overall system health
curl -f https://api.llm-platform.com/health

# Check specific service health
kubectl get pods -n llm-api-prod
kubectl describe pod <pod-name> -n llm-api-prod

# Check service logs
kubectl logs -f deployment/fastapi-deployment -n llm-api-prod
kubectl logs -f deployment/django-deployment -n llm-api-prod
```

### Monitoring Dashboard URLs
- **Service Health**: https://grafana.llm-platform.com/d/system-health
- **API Metrics**: https://grafana.llm-platform.com/d/api-performance
- **Infrastructure**: https://grafana.llm-platform.com/d/infrastructure

## Common Issues & Solutions

### 1. API Errors

#### 401 Unauthorized Errors

**Symptoms**:
```json
{
  "error": {
    "message": "Invalid authentication credentials",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

**Diagnosis**:
```bash
# Check API key validity
curl -H "X-API-Key: YOUR_KEY" https://api.llm-platform.com/v1/models

# Check authentication service logs
kubectl logs -l app=django-auth -n llm-api-prod --since=10m
```

**Solutions**:
1. Verify API key is correct and active
2. Check key hasn't expired
3. Ensure proper header format: `X-API-Key: your_key_here`
4. Check rate limiting isn't blocking requests

#### 429 Rate Limit Exceeded

**Symptoms**:
```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

**Diagnosis**:
```bash
# Check rate limiting metrics
curl -s "http://prometheus:9090/api/v1/query?query=rate_limit_violations_total"

# Check Redis rate limit counters
redis-cli -h redis-cluster KEYS "ratelimit:*"
```

**Solutions**:
1. Implement exponential backoff in client
2. Upgrade to higher tier plan
3. Optimize request patterns
4. Use caching to reduce API calls

#### 500 Internal Server Error

**Symptoms**:
```json
{
  "error": {
    "message": "Internal server error",
    "type": "server_error",
    "code": "internal_error"
  }
}
```

**Diagnosis**:
```bash
# Check application logs
kubectl logs -f deployment/fastapi-deployment -n llm-api-prod | grep ERROR
kubectl logs -f deployment/django-deployment -n llm-api-prod | grep ERROR

# Check resource utilization
kubectl top pods -n llm-api-prod

# Check database connectivity
kubectl exec -it deployment/django-deployment -- python manage.py dbshell
```

**Solutions**:
1. Check application logs for specific error
2. Verify database connectivity
3. Check resource constraints (CPU/memory)
4. Restart affected services if needed

### 2. Performance Issues

#### Slow Response Times

**Symptoms**:
- API responses taking >5 seconds
- Timeout errors
- High P95 latency in monitoring

**Diagnosis**:
```bash
# Check response time metrics
curl -w "Response time: %{time_total}s\n" \
     -H "X-API-Key: YOUR_KEY" \
     https://api.llm-platform.com/v1/models

# Check database performance
kubectl exec -it postgres-pod -- psql -c "
  SELECT query, mean_time, calls
  FROM pg_stat_statements
  ORDER BY mean_time DESC LIMIT 10;"

# Check cache hit rates
redis-cli -h redis-cluster INFO stats | grep cache_hits
```

**Solutions**:
1. Optimize database queries
2. Increase cache TTL values
3. Scale up infrastructure
4. Implement query optimization

#### Model Inference Timeouts

**Symptoms**:
- Chat completions timing out
- Model loading failures
- GPU memory errors

**Diagnosis**:
```bash
# Check GPU utilization
kubectl exec -it fastapi-pod -- nvidia-smi

# Check model loading logs
kubectl logs deployment/fastapi-deployment | grep "model.*load"

# Check inference metrics
curl "http://prometheus:9090/api/v1/query?query=model_inference_duration_seconds"
```

**Solutions**:
1. Increase timeout values
2. Optimize model quantization
3. Scale GPU resources
4. Implement model caching

### 3. Infrastructure Issues

#### Pod Crashes/Restarts

**Symptoms**:
- Frequent pod restarts
- `CrashLoopBackOff` status
- Service unavailability

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n llm-api-prod -w

# Check pod events
kubectl describe pod <pod-name> -n llm-api-prod

# Check resource constraints
kubectl top pods -n llm-api-prod

# Check previous container logs
kubectl logs <pod-name> -n llm-api-prod --previous
```

**Solutions**:
1. Increase resource limits
2. Fix application errors
3. Adjust health check parameters
4. Check persistent storage issues

#### Database Connection Issues

**Symptoms**:
- Database connection timeouts
- `FATAL: too many connections` errors
- Slow query performance

**Diagnosis**:
```bash
# Check database connections
kubectl exec -it postgres-pod -- psql -c "
  SELECT count(*) as active_connections,
         state
  FROM pg_stat_activity
  GROUP BY state;"

# Check connection pool status
kubectl logs deployment/django-deployment | grep "connection pool"

# Check database locks
kubectl exec -it postgres-pod -- psql -c "
  SELECT blocked_locks.pid AS blocked_pid,
         blocking_locks.pid AS blocking_pid,
         blocked_activity.query AS blocked_statement
  FROM pg_catalog.pg_locks blocked_locks
  JOIN pg_catalog.pg_stat_activity blocked_activity
    ON blocked_activity.pid = blocked_locks.pid;"
```

**Solutions**:
1. Increase connection pool size
2. Optimize long-running queries
3. Kill blocking queries if needed
4. Scale database resources

### 4. Security Issues

#### Authentication Failures

**Symptoms**:
- JWT token validation errors
- API key validation failures
- Authorization errors

**Diagnosis**:
```bash
# Check authentication service health
kubectl get pods -l app=auth-service -n llm-api-prod

# Check JWT token validity
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq .

# Check authentication logs
kubectl logs -l app=django-auth | grep "auth"
```

**Solutions**:
1. Verify token hasn't expired
2. Check token signing key
3. Validate token format
4. Check user permissions

#### SSL/TLS Issues

**Symptoms**:
- Certificate validation errors
- SSL handshake failures
- Mixed content warnings

**Diagnosis**:
```bash
# Check certificate validity
openssl s_client -connect api.llm-platform.com:443 -servername api.llm-platform.com

# Check certificate expiration
echo | openssl s_client -connect api.llm-platform.com:443 2>/dev/null | \
  openssl x509 -noout -dates

# Check ingress SSL configuration
kubectl describe ingress api-ingress -n llm-api-prod
```

**Solutions**:
1. Renew expired certificates
2. Update certificate chain
3. Fix ingress configuration
4. Update DNS records

## Diagnostic Tools & Commands

### Service Logs
```bash
# Stream logs from all services
kubectl logs -f -l app=fastapi-service -n llm-api-prod
kubectl logs -f -l app=django-service -n llm-api-prod

# Get logs from specific time period
kubectl logs --since=1h deployment/fastapi-deployment -n llm-api-prod

# Search logs for errors
kubectl logs deployment/fastapi-deployment -n llm-api-prod | grep -i error
```

### Metrics Queries
```bash
# Prometheus queries for common metrics
curl "http://prometheus:9090/api/v1/query?query=up"
curl "http://prometheus:9090/api/v1/query?query=rate(http_requests_total[5m])"
curl "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95, http_request_duration_seconds_bucket)"
```

### Database Diagnostics
```sql
-- Check slow queries
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
WHERE mean_time > 1000  -- queries taking more than 1 second
ORDER BY mean_time DESC
LIMIT 10;

-- Check database size
SELECT pg_size_pretty(pg_database_size('llm_api')) as database_size;

-- Check table sizes
SELECT schemaname,tablename,
       pg_size_pretty(size) as size_pretty,
       pg_size_pretty(total_size) as total_size_pretty
FROM (
  SELECT schemaname,tablename,
         pg_relation_size(schemaname||'.'||tablename) as size,
         pg_total_relation_size(schemaname||'.'||tablename) as total_size
  FROM pg_tables
) AS table_sizes
ORDER BY total_size DESC;
```

### Redis Diagnostics
```bash
# Check Redis memory usage
redis-cli -h redis-cluster INFO memory

# Check cache hit rate
redis-cli -h redis-cluster INFO stats | grep -E "(hits|misses)"

# Check slow log
redis-cli -h redis-cluster SLOWLOG GET 10

# Monitor commands in real-time
redis-cli -h redis-cluster MONITOR
```

## Performance Optimization

### API Response Time Optimization

1. **Enable Response Caching**:
   ```python
   # Add caching headers
   @cache_for(300)  # 5 minutes
   def list_models():
       return get_available_models()
   ```

2. **Optimize Database Queries**:
   ```python
   # Use select_related for foreign keys
   users = User.objects.select_related('organization').all()

   # Use prefetch_related for many-to-many
   users = User.objects.prefetch_related('api_keys').all()
   ```

3. **Implement Connection Pooling**:
   ```python
   # Configure connection pool
   DATABASES = {
       'default': {
           'OPTIONS': {
               'MAX_CONNS': 20,
               'MIN_CONNS': 5,
           }
       }
   }
   ```

### Model Inference Optimization

1. **Model Quantization**:
   ```python
   # Load quantized model
   model = AutoModelForCausalLM.from_pretrained(
       model_name,
       load_in_4bit=True,
       device_map="auto"
   )
   ```

2. **Batch Processing**:
   ```python
   # Process multiple requests together
   responses = model.generate(
       batch_inputs,
       max_length=max_tokens,
       batch_size=8
   )
   ```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Application Metrics**:
   - Request rate and latency
   - Error rate
   - Active connections
   - Queue depth

2. **Infrastructure Metrics**:
   - CPU and memory usage
   - Disk I/O and space
   - Network throughput
   - GPU utilization

3. **Business Metrics**:
   - API usage per customer
   - Token consumption
   - Revenue metrics
   - User activity

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Response Time P95 | >2s | >5s |
| Error Rate | >5% | >15% |
| CPU Usage | >80% | >95% |
| Memory Usage | >85% | >95% |
| Disk Usage | >80% | >95% |

## Emergency Procedures

### Service Outage Response

1. **Immediate Actions**:
   ```bash
   # Check service status
   kubectl get pods -n llm-api-prod

   # Scale up if needed
   kubectl scale deployment fastapi-deployment --replicas=5 -n llm-api-prod

   # Check recent deployments
   kubectl rollout history deployment/fastapi-deployment -n llm-api-prod
   ```

2. **Communication**:
   - Update status page
   - Notify stakeholders
   - Prepare incident report

3. **Recovery**:
   ```bash
   # Rollback if deployment caused issue
   kubectl rollout undo deployment/fastapi-deployment -n llm-api-prod

   # Restart services
   kubectl rollout restart deployment/fastapi-deployment -n llm-api-prod
   ```

### Data Recovery

1. **Database Recovery**:
   ```bash
   # Restore from backup
   pg_restore -h postgres-host -U postgres -d llm_api backup_file.sql
   ```

2. **Model Recovery**:
   ```bash
   # Restore models from object storage
   aws s3 sync s3://model-backup/ /data/models/
   ```

## Getting Help

### Internal Resources
- **Runbooks**: `/docs/operations/runbooks/`
- **Architecture Docs**: `/docs/architecture/`
- **API Documentation**: `/docs/api/`

### External Support
- **Status Page**: https://status.llm-platform.com
- **Support Email**: support@llm-platform.com
- **Emergency Hotline**: +1-555-LLM-HELP

### Escalation Procedures
1. **Level 1**: On-call engineer
2. **Level 2**: Senior engineer/Team lead
3. **Level 3**: Engineering manager
4. **Level 4**: CTO/Executive team

Remember: Always document issues and resolutions for future reference!