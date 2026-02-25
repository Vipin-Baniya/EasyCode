# Deployment Guide

## Production Deployment

### Environment Variables

Ensure all production environment variables are set:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=<generate-strong-random-key>
JWT_SECRET=<generate-strong-random-key>
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Optional but recommended
SENTRY_DSN=https://...
ENVIRONMENT=production
DEBUG=false
```

### Docker Deployment

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Run in production mode
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec backend alembic upgrade head
```

### Cloud Deployment

#### AWS / GCP / Azure

1. Set up managed PostgreSQL database
2. Set up Redis (managed or ElastiCache)
3. Deploy backend as container service
4. Deploy frontend to CDN/static hosting
5. Configure environment variables
6. Set up SSL/TLS certificates
7. Configure domain and DNS

#### Recommended Architecture

```
┌─────────────┐
│   CloudFlare│
│    (CDN)    │
└──────┬──────┘
       │
┌──────▼───────┐
│  Load Balancer
└──────┬───────┘
       │
┌──────▼───────┬──────────┬──────────┐
│  Backend 1   │Backend 2 │Backend 3 │
└──────┬───────┴──────┬───┴────┬─────┘
       │              │        │
┌──────▼──────────────▼────────▼─────┐
│          PostgreSQL (RDS)          │
└────────────────────────────────────┘
       │
┌──────▼──────────┐
│  Redis (Managed) │
└──────────────────┘
```

### Security Checklist

- [ ] Change all default passwords
- [ ] Use strong random secrets
- [ ] Enable HTTPS only
- [ ] Configure CORS properly
- [ ] Set up rate limiting
- [ ] Enable database backups
- [ ] Set up monitoring
- [ ] Configure logging
- [ ] Review permissions
- [ ] Enable 2FA for admin accounts

### Monitoring

1. Set up Sentry for error tracking
2. Configure Prometheus for metrics
3. Set up log aggregation
4. Configure alerts
5. Monitor API performance
6. Track LLM usage costs

### Backup Strategy

- Daily database backups
- Workspace snapshots
- Configuration backups
- Disaster recovery plan
