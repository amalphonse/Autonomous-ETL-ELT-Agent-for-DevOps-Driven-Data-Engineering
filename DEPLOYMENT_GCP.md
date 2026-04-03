# GCP Deployment Guide

This guide covers deploying the Autonomous ETL/ELT Agent on Google Cloud Platform (GCP) using multiple approaches.

## Table of Contents
1. [Quick Start: Cloud Run (Easiest)](#quick-start-cloud-run)
2. [Production: GKE (Kubernetes)](#production-gke)
3. [Database: Cloud SQL](#database-cloud-sql)
4. [Container Registry: Artifact Registry](#container-registry)
5. [CI/CD: Cloud Build](#cicd-cloud-build)
6. [Security: Secrets & Permissions](#security)
7. [Monitoring & Observability](#monitoring)
8. [Cost Estimation](#cost-estimation)

---

## Quick Start: Cloud Run

**Best for**: Demo, small teams, rapid iteration  
**Pros**: Serverless, auto-scaling, pay-per-use, minimal ops  
**Cons**: Limited execution time (60 min), no background tasks, limited disk (512MB)

### Prerequisites

```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate and set project
gcloud auth login
gcloud config set project PROJECT_ID

# Replace PROJECT_ID with your GCP project ID
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"  # or your preferred region
```

### Step 1: Build and Push Container Image

```bash
# Enable Container Registry API
gcloud services enable artifactregistry.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create etl-agent-repo \
  --repository-format=docker \
  --location=$REGION \
  --description="ETL Agent Docker images"

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest .

docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest
```

### Step 2: Prepare Environment Variables

Create `.env.cloud-run`:
```bash
# LLM Configuration
OPENAI_API_KEY=sk-...

# GitHub Configuration
GITHUB_TOKEN=ghp_...
GITHUB_REPO_URL=https://github.com/your-org/your-repo
GITHUB_BRANCH=main

# API Configuration
API_KEY=your-secure-api-key-here

# Database (will use Cloud SQL until next step)
DATABASE_URL=postgresql://user:password@cloudsql-ip/etl_db
DATABASE_DRIVER=postgresql

# API Settings
API_PORT=8000
API_HOST=0.0.0.0

# Environment
ENVIRONMENT=production
```

### Step 3: Create Cloud Run Service

```bash
# Deploy FastAPI backend
gcloud run deploy etl-api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --env-vars-file .env.cloud-run \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 1

# Deploy Streamlit frontend
gcloud run deploy etl-dashboard \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 900 \
  --max-instances 5

# Note: For Streamlit, use: streamlit run streamlit_app.py --server.headless true
```

### Step 4: Configure Streamlit

Create `streamlit_config.toml`:
```toml
[server]
headless = true
port = 8501
address = "0.0.0.0"
baseUrlPath = ""
enableXsrfProtection = true

[client]
toolbarMode = "minimal"

[theme]
base = "light"
primaryColor = "#FF6B35"
backgroundColor = "#FFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

### Step 5: Get Service URLs

```bash
# Get API endpoint
gcloud run services describe etl-api --region $REGION --format 'value(status.url)'

# Get Dashboard endpoint
gcloud run services describe etl-dashboard --region $REGION --format 'value(status.url)'
```

---

## Production: GKE

**Best for**: Production, complex workloads, control, multi-region  
**Pros**: Full Kubernetes flexibility, persistent volumes, network policies, autoscaling  
**Cons**: More operational overhead, higher baseline cost

### Prerequisites

```bash
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

### Step 1: Create GKE Cluster

```bash
# Create cluster (adjust specs for your needs)
gcloud container clusters create etl-agent-cluster \
  --region $REGION \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10 \
  --enable-autorepair \
  --enable-autoupgrade \
  --addons HorizontalPodAutoscaling,HttpLoadBalancing \
  --workload-pool=${PROJECT_ID}.svc.id.goog

# Get credentials
gcloud container clusters get-credentials etl-agent-cluster --region $REGION
```

### Step 2: Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace etl-agent

# Create secrets from environment file
kubectl create secret generic etl-secrets \
  --from-env-file=.env.cloud-run \
  -n etl-agent

# Create image pull secret for Artifact Registry
gcloud auth configure-docker
kubectl create secret docker-registry gcr-secret \
  --docker-server=${REGION}-docker.pkg.dev \
  --docker-username=_json_key \
  --docker-password="$(cat ~/.config/gcloud/legacy_credentials/*/adc.json)" \
  -n etl-agent
```

### Step 3: Update Kubernetes Manifests

Update `k8s/deployment.yaml` for GCP:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: etl-api
  namespace: etl-agent
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: etl-api
  template:
    metadata:
      labels:
        app: etl-api
    spec:
      imagePullSecrets:
        - name: gcr-secret
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - etl-api
                topologyKey: kubernetes.io/hostname
      containers:
        - name: etl-api
          image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
          env:
            - name: ENVIRONMENT
              value: production
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: etl-secrets
                  key: DATABASE_URL
            # Add other environment variables
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            allowPrivilegeEscalation: false
```

### Step 4: Deploy to GKE

```bash
# Set environment variables in manifests
export IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest

# Apply manifests
kubectl apply -f k8s/secrets.yaml -n etl-agent
kubectl apply -f k8s/deployment.yaml -n etl-agent
kubectl apply -f k8s/service.yaml -n etl-agent
kubectl apply -f k8s/hpa.yaml -n etl-agent

# Verify deployment
kubectl get pods -n etl-agent
kubectl logs -f deployment/etl-api -n etl-agent

# Get service endpoint
kubectl get svc -n etl-agent
```

### Step 5: Configure Ingress

Create `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: etl-ingress
  namespace: etl-agent
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    kubernetes.io/ingress.global-static-ip-name: "etl-api-ip"
spec:
  ingressClassName: "gce"
  tls:
    - hosts:
        - etl-api.your-domain.com
      secretName: etl-tls
  rules:
    - host: etl-api.your-domain.com
      http:
        paths:
          - path: /*
            pathType: ImplementationSpecific
            backend:
              service:
                name: etl-api
                port:
                  number: 8000
```

Deploy ingress:
```bash
kubectl apply -f k8s/ingress.yaml

# Reserve static IP
gcloud compute addresses create etl-api-ip --global

# Get IP and update DNS
gcloud compute addresses describe etl-api-ip --global
```

---

## Database: Cloud SQL

**Recommended for**: Production deployments

### Step 1: Create Cloud SQL Instance

```bash
# Enable Cloud SQL API
gcloud services enable sqladmin.googleapis.com

# Create PostgreSQL instance
gcloud sql instances create etl-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --backup \
  --backup-start-time=03:00 \
  --enable-bin-log \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=02
```

### Step 2: Create Database and User

```bash
# Create database
gcloud sql databases create etl_db \
  --instance=etl-postgres

# Create user
gcloud sql users create etl_user \
  --instance=etl-postgres \
  --password=$(openssl rand -base64 32)

# Get password and connection string
gcloud sql users describe etl_user --instance=etl-postgres
gcloud sql instances describe etl-postgres --format="value(connectionName)"
```

### Step 3: For GKE Workload Identity

```bash
# Create service account
gcloud iam service-accounts create etl-sa
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:etl-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/cloudsql.client

# Bind to Kubernetes service account
gcloud iam service-accounts add-iam-policy-binding \
  etl-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${PROJECT_ID}.svc.id.goog[etl-agent/etl-api]"

# Update k8s deployment
kubectl annotate serviceaccount etl-api \
  -n etl-agent \
  iam.gke.io/gcp-service-account=etl-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### Step 4: Update Connection String

```bash
# For GKE with Cloud SQL Proxy
DATABASE_URL=postgresql://etl_user:password@/etl_db?host=/cloudsql/${PROJECT_ID}:${REGION}:etl-postgres

# For Cloud Run with Cloud SQL Connector
DATABASE_URL=postgresql+psycopg2://etl_user:password@${INSTANCE_CONNECTION_NAME}/etl_db
```

---

## Container Registry

### Build and Push with Cloud Build

```bash
# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Build using Cloud Build (faster, no local docker daemon needed)
gcloud builds submit . \
  --tag=${REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest

# Or with custom build configuration
gcloud builds submit . \
  --config=cloudbuild.yaml
```

Create `cloudbuild.yaml`:

```yaml
steps:
  # Build image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:$SHORT_SHA'
      - '-t'
      - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest'
      - '.'

  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:$SHORT_SHA'

  # Deploy to GKE (if desired)
  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - run
      - --filename=k8s/
      - --image=${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:$SHORT_SHA
      - --location=$_REGION
      - --cluster=etl-agent-cluster
      - --namespace=etl-agent

images:
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:$SHORT_SHA'
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/etl-agent-repo/etl-api:latest'

substitutions:
  _REGION: us-central1

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: N1_HIGHCPU_8
```

---

## CI/CD: Cloud Build

### Automated Deployment on Git Push

Create `.gcloudignore`:
```
.git
.venv
__pycache__
*.pyc
.pytest_cache
.env.example
```

Setup GitHub integration:

```bash
# Install Cloud Build GitHub App
# Visit: https://console.cloud.google.com/cloud-build/triggers

# Create trigger via console:
# 1. Connect GitHub repo
# 2. Create new trigger:
#    - Name: etl-agent-deploy
#    - Event: Push to main branch
#    - Build config: Cloud Build configuration file
#    - Cloud Build config file location: cloudbuild.yaml
```

---

## Security

### Secrets Management

```bash
# Create Secret Manager secrets
echo -n "sk-..." | gcloud secrets create openai-api-key \
  --replication-policy="automatic" \
  --data-file=-

echo -n "ghp_..." | gcloud secrets create github-token \
  --replication-policy="automatic" \
  --data-file=-

# Grant access to Cloud Run and GKE
gcloud secrets add-iam-policy-binding openai-api-key \
  --member=serviceAccount:etl-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Update Kubernetes Manifests

```yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: etl-secrets
        key: openai-api-key
```

### Network Security

```bash
# Create VPC and subnets
gcloud compute networks create etl-vpc \
  --subnet-mode=custom

gcloud compute networks subnets create etl-subnet \
  --network=etl-vpc \
  --range=10.0.0.0/20 \
  --region=$REGION

# Create firewall rules
gcloud compute firewall-rules create allow-http \
  --network=etl-vpc \
  --allow=tcp:80,tcp:443

# Use in GKE cluster creation
gcloud container clusters create etl-agent-cluster \
  --network=etl-vpc \
  --subnetwork=etl-subnet \
  # ... other flags
```

---

## Monitoring & Observability

### CloudLogging Setup

```bash
# Enable Cloud Logging API
gcloud services enable logging.googleapis.com

# Logs automatically collected from:
# - Cloud Run: Container stderr/stdout
# - GKE: Through Kubernetes logging
# - Cloud SQL: Database query logs

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=etl-api" \
  --limit 50 \
  --format json

kubectl logs -f deployment/etl-api -n etl-agent
```

### Cloud Monitoring (Metrics)

```bash
# Enable Cloud Monitoring API
gcloud services enable monitoring.googleapis.com

# Create dashboard
gcloud monitoring dashboards create --config-from-file=monitoring-config.json
```

Create `monitoring-config.json`:

```json
{
  "displayName": "ETL Agent Dashboard",
  "gridLayout": {
    "widgets": [
      {
        "title": "API Request Count",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"etl-api\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "API Response Time (p95)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"custom.googleapis.com/pipeline/latency_p95\"",
                  "aggregation": {
                    "alignmentPeriod": "60s"
                  }
                }
              }
            }
          ]
        }
      }
    ]
  }
}
```

### Alerts

```bash
# Create alert policy for high CPU
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="High CPU Usage" \
  --condition-display-name="CPU > 80%" \
  --condition-threshold-value=0.8 \
  --condition-threshold-filter='resource.type="k8s_container" AND metric.type="kubernetes.io/container/cpu/core_usage_time"'
```

---

## Cost Estimation

### Monthly Cost Breakdown (us-central1)

| Component | Estimate | Notes |
|-----------|----------|-------|
| **Cloud Run** | $5-50 | Based on 100K-1M requests/month |
| **GKE (3 nodes, n1-standard-2)** | $200+ | Always running; storage extra |
| **Cloud SQL (db-f1-micro)** | $20-40 | Includes automated backups |
| **Artifact Registry** | $0.50 | Storage per GB |
| **Cloud Build** | $0.003/min | Free tier: 120 min/day |
| **Cloud Logging** | $0.50-5 | Depends on log volume |
| **Data Transfer** | $0.12/GB | Egress only |
| **Total (Cloud Run)** | $30-150 | Low-cost option |
| **Total (GKE)** | $250-500+ | Production option |

**Cost Optimization Tips:**
- Use Cloud Run for demos and tests
- Use GKE for production with reserved instances (30% savings)
- Enable autoscaling to match traffic
- Use Cloud SQL shared instances for dev/test
- Implement request logging/monitoring to identify waste

---

## Deployment Checklist

- [ ] GCP project created and billing enabled
- [ ] Required APIs enabled (Cloud Run, Container Registry, Cloud SQL, etc.)
- [ ] Docker image built and pushed to Artifact Registry
- [ ] Environment variables configured (.env.cloud-run)
- [ ] Secrets created in Secret Manager
- [ ] Database provisioned (Cloud SQL)
- [ ] Service deployed (Cloud Run or GKE)
- [ ] Health checks configured and passing
- [ ] Monitoring and logging enabled
- [ ] SSL/TLS certificates installed
- [ ] Backup and disaster recovery plan documented
- [ ] Cost monitoring alerts configured
- [ ] Team access and IAM roles assigned

---

## Troubleshooting

### Cloud Run Issues

```bash
# Check service logs
gcloud run services describe etl-api --region=$REGION

# View deployment logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=etl-api" --limit 100

# Test health endpoint
curl https://etl-api-xxxxx.a.run.app/health
```

### GKE Issues

```bash
# Check pod status
kubectl describe pod -n etl-agent

# Check events
kubectl get events -n etl-agent

# SSH into node
gcloud compute ssh gke-node-name

# Check HPA status
kubectl describe hpa -n etl-agent
```

### Database Connection Issues

```bash
# Test Cloud SQL connection
gcloud sql connect etl-postgres --user=etl_user

# Check service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --format='table(bindings.role)' \
  --filter="bindings.members:etl-sa*"
```

---

## Next Steps

1. **Start with Cloud Run** for rapid deployment
2. **Migrate to GKE** once production requirements are clear
3. **Add CI/CD** with Cloud Build for automated deployments
4. **Implement monitoring** and alerting from day one
5. **Plan disaster recovery** with backups and failover

For detailed GCP documentation, see: https://cloud.google.com/docs
