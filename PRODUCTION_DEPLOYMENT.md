# 🚀 Cloud Run Production Deployment Runbook

This guide provides step-by-step instructions to deploy the Autonomous ETL/ELT Agent to Google Cloud Run (Option 1).

## 📋 Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- [Docker](https://docs.docker.com/get-docker/)
- GCP Project with billing enabled
- OpenAI API key (sk-...)
- GitHub Personal Access Token (ghp_...)
- GCP Project ID

## ⚡ Quick Start (5 minutes)

### Step 1: Authenticate with GCP

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable cloudrun.googleapis.com artifactregistry.googleapis.com
```

### Step 2: Use Automated Deployment Script

```bash
cd /path/to/autonomous_ETL_ELT_DevOps_Project

# Run the deployment script
./deploy-cloud-run.sh

# Follow prompts for:
# - Project ID
# - Region (default: us-central1)
# - Production mode (y/n)
# - API credentials
```

**That's it!** The script handles:
- ✅ Building Docker image
- ✅ Pushing to Artifact Registry
- ✅ Creating secrets
- ✅ Deploying FastAPI API
- ✅ Deploying Streamlit dashboard

---

## 📊 Manual Deployment (Detailed Steps)

If you prefer manual control, follow these steps:

### Step 1: Prepare Environment

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export IMAGE_REPO="etl-agent-repo"

gcloud config set project $PROJECT_ID
```

### Step 2: Create Artifact Registry

```bash
# Create Docker registry
gcloud artifacts repositories create $IMAGE_REPO \
  --repository-format=docker \
  --location=$REGION

# Configure Docker auth
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### Step 3: Build and Push Docker Image

```bash
# Build image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPO}/etl-api:latest .

# Push to registry
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPO}/etl-api:latest
```

### Step 4: Create Secrets (Optional but Recommended)

```bash
# Enable Secret Manager
gcloud services enable secretmanager.googleapis.com

# Create secrets
echo "sk-proj-YOUR_KEY" | gcloud secrets create openai-api-key --data-file=-
echo "ghp_YOUR_TOKEN" | gcloud secrets create github-token --data-file=-
echo "your-secure-api-key" | gcloud secrets create api-key --data-file=-
```

### Step 5: Deploy API Service

```bash
# Prepare image URL
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPO}/etl-api:latest"

# Deploy API
gcloud run deploy etl-api \
  --image=$IMAGE_URL \
  --platform=managed \
  --region=$REGION \
  --memory=1Gi \
  --cpu=1 \
  --timeout=3600 \
  --max-instances=10 \
  --allow-unauthenticated \
  --set-env-vars=\
ENVIRONMENT=production,\
OPENAI_API_KEY=sk-YOUR_KEY,\
GITHUB_TOKEN=ghp_YOUR_TOKEN,\
API_KEY=secure-key \
  --no-allow-unauthenticated  # Comment out for development

# Get API URL
API_URL=$(gcloud run services describe etl-api \
  --region=$REGION \
  --format='value(status.url)')

echo "API deployed at: $API_URL"
```

### Step 6: Deploy Streamlit Dashboard

```bash
# Deploy frontend
gcloud run deploy etl-dashboard \
  --image=$IMAGE_URL \
  --platform=managed \
  --region=$REGION \
  --memory=512Mi \
  --cpu=1 \
  --max-instances=5 \
  --allow-unauthenticated \
  --set-env-vars=\
API_URL=$API_URL,\
ENVIRONMENT=production,\
API_KEY=secure-key \
  --entrypoint="streamlit" \
  --args="run,streamlit_app.py,--logger.level=error,--server.headless=true"

# Get dashboard URL
DASHBOARD_URL=$(gcloud run services describe etl-dashboard \
  --region=$REGION \
  --format='value(status.url)')

echo "Dashboard deployed at: $DASHBOARD_URL"
```

---

## 🧪 Testing Deployment

### Test API Health

```bash
# Replace with your actual API URL
curl https://etl-api-xxxxx.a.run.app/health

# Expected response
# {
#   "status": "healthy",
#   "service": "Autonomous ETL/ELT Agent",
#   "version": "1.0.0",
#   "environment": "production",
#   "database": "sqlite",
#   "database_connected": true
# }
```

### Test Demo Endpoint

```bash
# Test with Bearer token
curl -X POST https://etl-api-xxxxx.a.run.app/pipelines/demo \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Pipeline",
    "description": "Test transformation",
    "source_system": "Test Source",
    "target_system": "Test Target"
  }'
```

### Open Dashboard

```bash
# Open in browser
echo "https://etl-dashboard-xxxxx.a.run.app"
```

---

## 🔐 Production Checklist

Before marking production-ready:

- [ ] **Security**
  - [ ] All secrets stored in GCP Secret Manager (not in source code)
  - [ ] API_KEY enforced on all endpoints
  - [ ] HTTPS/TLS enabled (automatic with Cloud Run)
  - [ ] No credentials in container images
  - [ ] .env file in .gitignore

- [ ] **Database**
  - [ ] PostgreSQL configured (not SQLite)
  - [ ] Cloud SQL instance created and healthy
  - [ ] Database backed up daily
  - [ ] Connection pooling configured

- [ ] **Monitoring**
  - [ ] Cloud Logging enabled
  - [ ] Error alerts configured
  - [ ] Performance metrics tracked
  - [ ] Uptime monitoring in place

- [ ] **Configuration**
  - [ ] ENVIRONMENT=production
  - [ ] LOG_LEVEL=WARNING
  - [ ] ALLOWED_ORIGINS restricted to specific domains
  - [ ] Max instances appropriate for load

- [ ] **Testing**
  - [ ] /health endpoint returns healthy
  - [ ] /pipelines/demo endpoint working
  - [ ] API key authentication working
  - [ ] Streamlit dashboard accessible
  - [ ] Error handling working correctly

---

## 📈 Scaling & Performance

### Increase Instance Count

```bash
# Update max instances
gcloud run services update etl-api \
  --region=$REGION \
  --max-instances=50
```

### Monitor Metrics

```bash
# View request metrics
gcloud run services describe etl-api --region=$REGION

# View CloudLogging
gcloud logging read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format json
```

### Set Up Alerts

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Cloud Run High Error Rate" \
  --condition-threshold-value=0.05
```

---

## 🐛 Troubleshooting

### API won't start

```bash
# Check logs
gcloud run logs read etl-api --region=$REGION

# Common issues:
# - Missing OPENAI_API_KEY environment variable
# - Database connection failed
# - Port not listening on 8000
```

### Dashboard can't connect to API

```bash
# Verify API URL environment variable
gcloud run services describe etl-dashboard --region=$REGION \
  --format='value(spec.template.spec.containers[0].env[name=API_URL])'

# Check CORS configuration
curl -H "Origin: https://etl-dashboard-xxxxx.a.run.app" \
     https://etl-api-xxxxx.a.run.app/health
```

### High memory usage

```bash
# Increase memory allocation
gcloud run services update etl-api \
  --memory=2Gi \
  --region=$REGION

# Check usage
gcloud monitoring read-time-series resource.labels.service_name=etl-api
```

---

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Security Best Practices](https://cloud.google.com/run/docs/securing/setup-gcp-resources)
- [Cloud SQL Proxy for Local Testing](https://cloud.google.com/sql/docs/postgres/sql-proxy)
- [Cloud Run Quotas](https://cloud.google.com/run/quotas)

---

## 💡 Cost Optimization Tips

1. **Use Cloud Run for variable load** (ideal for this use case)
2. **Set appropriate max instances** - start with 5-10, scale based on need
3. **Minimize memory allocation** - start with 512Mi, increase if needed
4. **Use PostgreSQL Cloud SQL shared instances** for dev/test
5. **Enable Cloud CDN** if dashboard gets heavy traffic
6. **Monitor and adjust** based on actual usage

---

## Next Steps

1. ✅ Run deployment script or follow manual steps
2. ✅ Test all endpoints and dashboard
3. ✅ Configure custom domain (optional)
4. ✅ Set up monitoring and alerting
5. ✅ Plan backup and disaster recovery
6. ✅ Document runbooks for operations team

---

**Deployment completed!** 🎉

Your production system is now running on Cloud Run. Monitor logs and metrics regularly to ensure optimal performance.
