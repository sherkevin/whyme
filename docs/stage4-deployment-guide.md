# Stage 4 Deployment Guide

## Overview

This guide covers deploying Stage 4 (Search, Ingestion, and Insight capabilities) of AgentOS PA 1.0.

**Table of Contents**:
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **CPU**: 2 cores minimum, 4 cores recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 20GB free space
- **OS**: Linux (Ubuntu 22.04 recommended), macOS, or Windows with WSL2

### Software Requirements

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+
- **PostgreSQL**: 15+ (if not using Docker)

---

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**:
```bash
git clone https://github.com/your-org/agentos.git
cd agentos
```

2. **Create environment file**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start all services**:
```bash
docker-compose -f docker-compose.search_engine.yml up -d
```

4. **Verify deployment**:
```bash
# Check API health
curl http://localhost:8000/health

# Check service status
docker-compose -f docker-compose.search_engine.yml ps
```

5. **Access the application**:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- pgAdmin: http://localhost:5050 (if enabled)

---

## Docker Deployment

### Building the Image

```bash
docker build -f Dockerfile.search_engine -t agentos-search_engine:latest .
```

### Running with Docker Compose

#### Basic Deployment
```bash
docker-compose -f docker-compose.search_engine.yml up -d
```

#### With All Optional Services
```bash
# Enable admin tools (pgAdmin)
docker-compose -f docker-compose.search_engine.yml --profile admin up -d

# Enable cache (Redis)
docker-compose -f docker-compose.search_engine.yml --profile cache up -d

# Enable proxy (Nginx)
docker-compose -f docker-compose.search_engine.yml --profile proxy up -d

# Enable all extras
docker-compose -f docker-compose.search_engine.yml --profile admin --profile cache --profile proxy up -d
```

### Environment Variables

Create a `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://agentos:your_password@postgres:5432/agentos_db
SYNC_DATABASE_URL=postgresql://agentos:your_password@postgres:5432/agentos_db

# Application
ENVIRONMENT=production
LOG_LEVEL=info
SECRET_KEY=your-secret-key-here

# Stage 4 Settings
ENABLE_VECTOR_SEARCH=false
AUTO_EMBED_INDEXING=true

# CORS
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Docker Volumes

| Volume | Description |
|--------|-------------|
| `postgres_data` | PostgreSQL data persistence |
| `pgadmin_data` | pgAdmin configuration |
| `redis_data` | Redis cache data |
| `./data` | Application data |
| `./logs` | Application logs |

---

## Manual Deployment

### Installing Dependencies

```bash
# Install Python 3.11
sudo apt update
sudo apt install -y python3.11 python3.11-dev python3-venv

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Setting Up PostgreSQL

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE agentos_db;
CREATE USER agentos WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE agentos_db TO agentos;
\q
EOF
```

### Running the Application

```bash
# Set environment variables
export DATABASE_URL="postgresql+asyncpg://agentos:your_password@localhost:5432/agentos_db"
export SYNC_DATABASE_URL="postgresql://agentos:your_password@localhost:5432/agentos_db"
export SECRET_KEY="your-secret-key"

# Run migrations (if using Alembic)
alembic upgrade head

# Start the server
uvicorn agent_os.server.app:app --host 0.0.0.0 --port 8000
```

### Using Systemd (Production)

Create `/etc/systemd/system/agentos.service`:

```ini
[Unit]
Description=AgentOS Stage 4 API
After=network.target postgresql.service

[Service]
Type=notify
User=agentos
WorkingDirectory=/opt/agentos
Environment="PATH=/opt/agentos/venv/bin"
EnvironmentFile=/opt/agentos/.env
ExecStart=/opt/agentos/venv/bin/uvicorn agent_os.server.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable agentos
sudo systemctl start agentos
sudo systemctl status agentos
```

---

## Configuration

### Application Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name |
| `LOG_LEVEL` | `info` | Logging level |
| `SECRET_KEY` | - | Secret key for authentication |
| `DATABASE_URL` | - | Async database URL |
| `ENABLE_VECTOR_SEARCH` | `false` | Enable semantic search |
| `AUTO_EMBED_INDEXING` | `true` | Auto-generate embeddings |

### Performance Tuning

#### PostgreSQL Configuration

Edit `postgresql.conf`:

```conf
# Memory
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB

# Connections
max_connections = 100

# Query Optimization
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000
```

#### Application Tuning

```python
# In agent_os/server/app.py

# Number of worker processes
workers = 4  # CPU cores * 2 + 1

# Max requests per worker before restart
max_requests = 1000
max_requests_jitter = 100

# Timeout settings
timeout_keep_alive = 30
timeout = 120
```

---

## Monitoring

### Health Checks

```bash
# API health endpoint
curl http://localhost:8000/health

# Expected response
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-08T10:00:00Z"
}
```

### Metrics

Key metrics to monitor:

**Search Metrics**:
- Search response time (p50, p95, p99)
- Search QPS
- Index size and growth rate
- Cache hit rate

**Ingestion Metrics**:
- Job success rate
- Average processing time
- Error types distribution
- Queue depth (if using background workers)

**Insight Metrics**:
- Generation time
- Cache hit rate
- Popular insight types

### Logging

Logs are stored in `./logs`:

```
logs/
├── agentos.log          # Main application log
├── access.log           # API access log
├── search_engine.log           # Stage 4 specific log
└── errors.log           # Error log
```

View logs:
```bash
# Follow logs
tail -f logs/agentos.log

# Search logs
grep "ERROR" logs/agentos.log

# Docker logs
docker-compose -f docker-compose.search_engine.yml logs -f agentos-api
```

### Monitoring Tools

**Prometheus + Grafana** (Optional):

Add to `docker-compose.search_engine.yml`:

```yaml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Problem**:
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**:
```bash
# Check PostgreSQL is running
docker-compose -f docker-compose.search_engine.yml ps postgres

# Check logs
docker-compose -f docker-compose.search_engine.yml logs postgres

# Verify DATABASE_URL
echo $DATABASE_URL
```

#### 2. Import Errors

**Problem**:
```
ModuleNotFoundError: No module named 'agent_os.search_engine'
```

**Solution**:
```bash
# Install in editable mode
pip install -e .

# Or reinstall
pip uninstall agent-os
pip install -e .
```

#### 3. Port Already in Use

**Problem**:
```
OSError: [Errno 48] Address already in use
```

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
docker-compose -f docker-compose.search_engine.yml config --services
```

#### 4. Out of Memory

**Problem**:
Container crashes with OOMKilled

**Solution**:
```yaml
# In docker-compose.search_engine.yml
services:
  agentos-api:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

#### 5. Slow Search Performance

**Problem**: Search takes > 1 second

**Solutions**:
1. Add database indexes:
```sql
CREATE INDEX CONCURRENTLY idx_search_title ON search_indices USING gin(to_tsvector('english', title));
CREATE INDEX CONCURRENTLY idx_search_content ON search_indices USING gin(to_tsvector('english', content));
```

2. Enable query caching
3. Reduce result page size
4. Use PostgreSQL full-text search instead of LIKE

### Debug Mode

Enable debug logging:

```bash
# Set environment
export LOG_LEVEL=debug

# Or in docker-compose.yml
environment:
  - LOG_LEVEL=debug
```

Restart service and check logs:
```bash
docker-compose -f docker-compose.search_engine.yml restart agentos-api
docker-compose -f docker-compose.search_engine.yml logs -f agentos-api
```

---

## Backup and Recovery

### Database Backup

```bash
# Backup
docker-compose -f docker-compose.search_engine.yml exec postgres \
  pg_dump -U agentos agentos_db > backup_$(date +%Y%m%d).sql

# Restore
docker-compose -f docker-compose.search_engine.yml exec -T postgres \
  psql -U agentos agentos_db < backup_20260208.sql
```

### Volume Backup

```bash
# Backup volumes
docker run --rm -v agentos_search_engine_postgres_data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/postgres_backup_$(date +%Y%m%d).tar.gz /data

# Restore volumes
docker run --rm -v agentos_search_engine_postgres_data:/data -v $(pwd):/backup \
  ubuntu tar xzf /backup/postgres_backup_20260208.tar.gz -C /
```

---

## Scaling

### Horizontal Scaling

Use multiple API instances behind a load balancer:

```bash
# Scale to 3 instances
docker-compose -f docker-compose.search_engine.yml up -d --scale agentos-api=3
```

### Database Scaling

**Read Replicas**:

```yaml
postgres-replica:
  image: postgres:15-alpine
  environment:
    - POSTGRES_REPLICA_MODE=true
    - POSTGRES_MASTER_HOST=postgres
```

**Connection Pooling**:

```yaml
pgbouncer:
  image: pgbouncer/pgbouncer:latest
  environment:
    - DATABASES_HOST=postgres
    - DATABASES_PORT=5432
    - DATABASES_USER=agentos
    - DATABASES_PASSWORD=agentos_password
    - DATABASES_DBNAME=agentos_db
```

---

## Security

### SSL/TLS Configuration

```nginx
# In nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://agentos-api:8000;
    }
}
```

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### Secrets Management

Use environment variables or secrets manager:

```bash
# Docker secrets
echo "your-secret-key" | docker secret create agentos_secret_key -

# Kubernetes secrets
kubectl create secret generic agentos-secrets \
  --from-literal=secret-key='your-secret-key'
```

---

## Updates and Maintenance

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.search_engine.yml down
docker-compose -f docker-compose.search_engine.yml build
docker-compose -f docker-compose.search_engine.yml up -d
```

### Database Migrations

```bash
# Run migrations
docker-compose -f docker-compose.search_engine.yml exec agentos-api \
  alembic upgrade head

# Rollback
docker-compose -f docker-compose.search_engine.yml exec agentos-api \
  alembic downgrade -1
```

---

## Support

For issues and questions:

- **Documentation**: https://docs.agentos.example.com
- **GitHub Issues**: https://github.com/your-org/agentos/issues
- **Discord**: https://discord.gg/agentos
- **Email**: support@agentos.example.com

---

## Appendix

### A. Environment Variables Reference

See `.env.example` for complete list.

### B. API Endpoints

See `/docs` endpoint or `docs/search_engine-api-guide.md`.

### C. Performance Benchmarks

See Stage 4 final report for baseline metrics.
