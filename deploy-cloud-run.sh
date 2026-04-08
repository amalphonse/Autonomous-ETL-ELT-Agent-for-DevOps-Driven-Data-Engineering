#!/bin/bash
# Deploy Autonomous ETL/ELT Agent to Google Cloud Run
# This script handles the complete Cloud Run deployment process

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================${NC}"
echo -e "${BLUE}Cloud Run Deployment Script${NC}"
echo -e "${BLUE}===================================${NC}"

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Install it from: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Install it from: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# Get configuration
echo -e "\n${YELLOW}Configuration:${NC}"

# Check if arguments provided
if [ $# -eq 0 ]; then
    read -p "Enter GCP Project ID: " PROJECT_ID
    read -p "Enter GCP Region (default: us-central1): " REGION
    REGION=${REGION:-us-central1}
    
    echo ""
    echo "Production Deployment? (requires PostgreSQL, API_KEY, etc.)"
    read -p "Production (y/n)? [n]: " IS_PROD
    IS_PROD=${IS_PROD:-n}
else
    PROJECT_ID=$1
    REGION=${2:-us-central1}
    IS_PROD=${3:-n}
fi

echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Production: $IS_PROD"

# Set gcloud project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "\n${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable \
    cloudrun.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com

# Create Artifact Registry repository
REGISTRY="etl-agent-repo"
echo -e "\n${YELLOW}Setting up container registry...${NC}"

if gcloud artifacts repositories describe $REGISTRY --location=$REGION &> /dev/null; then
    echo -e "${GREEN}✓${NC} Artifact Registry repository already exists"
else
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $REGISTRY \
        --repository-format=docker \
        --location=$REGION \
        --description="ETL Agent Docker images"
fi

# Configure Docker authentication
echo "Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build Docker image
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY}/etl-api:latest"

echo -e "\n${YELLOW}Building Docker image...${NC}"
echo "Image URL: $IMAGE_URL"

if docker build -t $IMAGE_URL .; then
    echo -e "${GREEN}✓${NC} Docker image built successfully"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Push image
echo -e "\n${YELLOW}Pushing image to Artifact Registry...${NC}"
if docker push $IMAGE_URL; then
    echo -e "${GREEN}✓${NC} Image pushed successfully"
else
    echo -e "${RED}❌ Docker push failed${NC}"
    exit 1
fi

# Create secrets
echo -e "\n${YELLOW}Setting up secrets...${NC}"

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if gcloud secrets describe $secret_name &> /dev/null; then
        echo "Updating existing secret: $secret_name"
        echo "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "Creating new secret: $secret_name"
        echo "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# Prompt for secrets
echo -e "\n${YELLOW}Enter production secrets (or leave blank to use environment variables):${NC}"
read -p "OpenAI API Key (sk-...): " OPENAI_API_KEY
read -p "GitHub Token (ghp_...): " GITHUB_TOKEN
read -p "GitHub Repo Owner: " GITHUB_REPO_OWNER
read -p "GitHub Repo Name: " GITHUB_REPO_NAME
read -p "GCP Project ID (for BigQuery): " GCP_PROJECT_ID
read -p "API Key for authentication: " API_KEY
read -p "Database URL (optional): " DATABASE_URL

# Create secrets if provided
if [ ! -z "$OPENAI_API_KEY" ]; then
    create_or_update_secret "openai-api-key" "$OPENAI_API_KEY"
fi

if [ ! -z "$GITHUB_TOKEN" ]; then
    create_or_update_secret "github-token" "$GITHUB_TOKEN"
fi

if [ ! -z "$API_KEY" ]; then
    create_or_update_secret "api-key" "$API_KEY"
fi

# Deploy to Cloud Run
echo -e "\n${YELLOW}Deploying to Cloud Run...${NC}"

# Determine environment and settings
if [ "$IS_PROD" = "y" ]; then
    ENVIRONMENT="production"
    INSTANCES="${6:-3}"
    MAX_INSTANCES="${7:-10}"
    MEMORY="2Gi"
    CPU="2"
    TIMEOUT="3600"
    ALLOW_UNAUTHENTICATED="false"
else
    ENVIRONMENT="development"
    INSTANCES="1"
    MAX_INSTANCES="5"
    MEMORY="1Gi"
    CPU="1"
    TIMEOUT="900"
    ALLOW_UNAUTHENTICATED="true"
fi

# Build environment variables
ENV_VARS="ENVIRONMENT=$ENVIRONMENT"

if [ ! -z "$OPENAI_API_KEY" ]; then
    ENV_VARS="$ENV_VARS,OPENAI_API_KEY=$OPENAI_API_KEY"
fi
if [ ! -z "$GITHUB_REPO_OWNER" ]; then
    ENV_VARS="$ENV_VARS,GITHUB_REPO_OWNER=$GITHUB_REPO_OWNER"
fi
if [ ! -z "$GITHUB_REPO_NAME" ]; then
    ENV_VARS="$ENV_VARS,GITHUB_REPO_NAME=$GITHUB_REPO_NAME"
fi
if [ ! -z "$GCP_PROJECT_ID" ]; then
    ENV_VARS="$ENV_VARS,GCP_PROJECT_ID=$GCP_PROJECT_ID"
fi
if [ ! -z "$DATABASE_URL" ]; then
    ENV_VARS="$ENV_VARS,DATABASE_URL=$DATABASE_URL"
fi

# Add CORS settings
ENV_VARS="$ENV_VARS,ALLOWED_ORIGINS=*"

echo -e "Deploying API service..."
gcloud run deploy etl-api \
    --image $IMAGE_URL \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated=$ALLOW_UNAUTHENTICATED \
    --memory $MEMORY \
    --cpu $CPU \
    --timeout $TIMEOUT \
    --max-instances $MAX_INSTANCES \
    --set-env-vars "$ENV_VARS" \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe etl-api --region=$REGION --format='value(status.url)')
echo -e "\n${GREEN}✓${NC} API deployed successfully!"
echo -e "${BLUE}API URL: $SERVICE_URL${NC}"

# Deploy Streamlit frontend
echo -e "\n${YELLOW}Deploying Streamlit dashboard...${NC}"

STREAMLIT_ENV_VARS="API_URL=$SERVICE_URL,ENVIRONMENT=$ENVIRONMENT"
if [ ! -z "$API_KEY" ]; then
    STREAMLIT_ENV_VARS="$STREAMLIT_ENV_VARS,API_KEY=$API_KEY"
fi

gcloud run deploy etl-dashboard \
    --image $IMAGE_URL \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated=true \
    --memory 512Mi \
    --cpu 1 \
    --timeout 600 \
    --max-instances 5 \
    --set-env-vars "$STREAMLIT_ENV_VARS" \
    --entrypoint "streamlit" \
    --args "run,streamlit_app.py,--logger.level=error,--server.headless=true" \
    --quiet

# Get dashboard URL
DASHBOARD_URL=$(gcloud run services describe etl-dashboard --region=$REGION --format='value(status.url)')
echo -e "\n${GREEN}✓${NC} Dashboard deployed successfully!"
echo -e "${BLUE}Dashboard URL: $DASHBOARD_URL${NC}"

# Summary
echo -e "\n${BLUE}===================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${BLUE}===================================${NC}"
echo ""
echo "📊 Service URLs:"
echo "  API:       $SERVICE_URL"
echo "  Dashboard: $DASHBOARD_URL"
echo ""
echo "🔧 Configuration:"
echo "  Environment:   $ENVIRONMENT"
echo "  Region:        $REGION"
echo "  Memory (API):  $MEMORY"
echo "  Memory (UI):   512Mi"
echo ""
echo "📝 Next steps:"
echo "  1. Test the API: curl $SERVICE_URL/health"
echo "  2. Open dashboard: $DASHBOARD_URL"
echo "  3. Monitor logs:  gcloud run logs read etl-api --region=$REGION"
echo ""
if [ "$IS_PROD" = "y" ]; then
    echo "⚠️  Production deployment:"
    echo "  - Ensure HTTPS is enforced"
    echo "  - Configure custom domain"
    echo "  - Set up monitoring and alerting"
    echo "  - Enable Cloud Firestore for persistent storage"
    echo ""
fi

echo -e "${GREEN}✅ All done!${NC}"
