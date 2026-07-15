#!/bin/bash
# Automated Deployment Script for Airco Insights on EC2
# Run this on the EC2 instance after cloning the repo

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Airco Insights EC2 Deployment ===${NC}"
echo ""

# Check if running as root (should not be)
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Error: Do not run as root. Use ubuntu user.${NC}"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing...${NC}"
    sudo apt update
    sudo apt install -y docker.io docker-compose git certbot
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed. Please logout and login again, then re-run this script.${NC}"
    exit 0
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo -e "${YELLOW}Adding user to docker group...${NC}"
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Please logout and login again, then re-run this script.${NC}"
    exit 0
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found. Are you in the project root?${NC}"
    exit 1
fi

PROJECT_DIR="/opt/airco"
echo -e "${YELLOW}Setting up project in ${PROJECT_DIR}...${NC}"

# Create necessary directories
sudo mkdir -p ${PROJECT_DIR}/ssl
sudo mkdir -p ${PROJECT_DIR}/data/postgres
sudo mkdir -p ${PROJECT_DIR}/data/minio
sudo chown -R $USER:$USER ${PROJECT_DIR}

# Copy current directory to /opt/airco if not already there
if [ "$PWD" != "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Copying files to ${PROJECT_DIR}...${NC}"
    sudo cp -r . ${PROJECT_DIR}/
    sudo chown -R $USER:$USER ${PROJECT_DIR}
    cd ${PROJECT_DIR}
fi

# Generate .env if it doesn't exist or update passwords
if [ ! -f ".env" ] || [ "$1" == "--reset-passwords" ]; then
    echo -e "${YELLOW}Generating secure environment file...${NC}"
    
    # Generate random passwords
    DB_PASS=$(openssl rand -base64 32)
    RMQ_PASS=$(openssl rand -base64 32)
    MINIO_PASS=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 48)
    KEYCLOAK_ADMIN_PASS=$(openssl rand -base64 16)
    
    cat > .env << EOF
# Public domain / routing
PUBLIC_DOMAIN=test.theairco.ai
NEXT_PUBLIC_API_URL=https://test.theairco.ai
BACKEND_URL=http://backend:8000
AUTH_SERVICE_URL=http://auth-service:8001
FILE_SERVICE_URL=http://file-service:8002
PDF_SERVICE_URL=http://pdf-service:8003
AI_SERVICE_URL=http://ai-service:8004
REPORT_SERVICE_URL=http://report-service:8005

# Keycloak public + internal wiring
KEYCLOAK_URL=https://test.theairco.ai
NEXT_PUBLIC_KEYCLOAK_URL=https://test.theairco.ai
NEXT_PUBLIC_KEYCLOAK_REALM=airco-insights
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=frontend-app
KEYCLOAK_REALM=airco-insights
KEYCLOAK_CLIENT_ID=frontend-app
KEYCLOAK_CLIENT_SECRET=airco-frontend-secret-2024-secure-key-abc123xyz
AUTH_SERVICE_KEYCLOAK_CLIENT_ID=frontend-app
AUTH_SERVICE_KEYCLOAK_CLIENT_SECRET=airco-frontend-secret-2024-secure-key-abc123xyz
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASS}
KEYCLOAK_DB_USERNAME=keycloak
KEYCLOAK_DB_PASSWORD=$(openssl rand -base64 16)
KC_HTTP_CORS_ORIGINS=https://test.theairco.ai
KC_HTTP_CORS_ALLOWED_ORIGINS=https://test.theairco.ai

# Application database
APP_DB_NAME=airco_app
APP_DB_USER=airco
APP_DB_PASSWORD=${DB_PASS}
AUTH_DATABASE_URL=postgresql://airco:${DB_PASS}@app-postgres:5432/auth_db
DATABASE_URL=postgresql://airco:${DB_PASS}@app-postgres:5432/airco_app
JWT_SECRET_KEY=${JWT_SECRET}

# Object storage / queues / cache
S3_ACCESS_KEY=airco_s3_access
S3_SECRET_KEY=$(openssl rand -base64 32)
S3_BUCKET=airco-files
MINIO_ACCESS_KEY=airco_minio_access
MINIO_SECRET_KEY=${MINIO_PASS}
MINIO_ENDPOINT=http://minio:9000
RABBITMQ_DEFAULT_USER=airco_rmq
RABBITMQ_DEFAULT_PASS=${RMQ_PASS}
REDIS_URL=redis://redis:6379
S3_ENDPOINT=http://minio:9000
S3_REGION=ap-south-1

# AI provider keys (must be set manually)
GROQ_API_KEY=REPLACE_ME
ANTHROPIC_API_KEY=REPLACE_ME
CLAUDE_API_KEY=REPLACE_ME
GOOGLE_API_KEY=REPLACE_ME
NEXT_PUBLIC_AIRCO_API_KEY=REPLACE_ME

# SSL on EC2 host
SSL_CERTS_DIR=/opt/airco/ssl
SSL_CERT_PATH=/opt/airco/ssl/fullchain.pem
SSL_KEY_PATH=/opt/airco/ssl/privkey.pem

# Optional model overrides
GROQ_MODEL=llama-3.3-70b-versatile
CLAUDE_MODEL=claude-3-sonnet-20240229

# Optional service tuning
DEBUG=false
STORAGE_TYPE=minio
MAX_FILE_SIZE_MB=20
PROCESSING_TIMEOUT_SECONDS=300
DEFAULT_ANALYSIS_TYPE=categorization
DEFAULT_REPORT_FORMAT=excel

# Data retention policy (7-day retention for raw PDFs and Excel reports)
DATA_RETENTION_DAYS=7
RETENTION_ENABLED=true
RETENTION_SWEEP_INTERVAL_MINUTES=60
EOF
    
    echo -e "${GREEN}Environment file created with secure passwords!${NC}"
    echo -e "${YELLOW}Keycloak Admin Password: ${KEYCLOAK_ADMIN_PASS}${NC}"
    echo -e "${YELLOW}Save this password - you will need it to access Keycloak admin console!${NC}"
    echo ""
fi

# Check and setup SSL certificates
if [ ! -f "ssl/fullchain.pem" ] || [ ! -f "ssl/privkey.pem" ]; then
    echo -e "${YELLOW}SSL certificates not found. Setting up Let's Encrypt...${NC}"
    
    # Check if certbot certificates exist
    if sudo test -f "/etc/letsencrypt/live/test.theairco.ai/fullchain.pem"; then
        echo -e "${YELLOW}Copying existing Let's Encrypt certificates...${NC}"
        sudo cp /etc/letsencrypt/live/test.theairco.ai/fullchain.pem ssl/
        sudo cp /etc/letsencrypt/live/test.theairco.ai/privkey.pem ssl/
        sudo chown $USER:$USER ssl/*.pem
    else
        echo -e "${YELLOW}Generating new SSL certificates with Let's Encrypt...${NC}"
        echo -e "${YELLOW}Make sure port 80 is open and domain points to this server.${NC}"
        
        sudo certbot certonly --standalone -d test.theairco.ai --agree-tos -n -m admin@theairco.ai
        
        if [ $? -eq 0 ]; then
            sudo cp /etc/letsencrypt/live/test.theairco.ai/fullchain.pem ssl/
            sudo cp /etc/letsencrypt/live/test.theairco.ai/privkey.pem ssl/
            sudo chown $USER:$USER ssl/*.pem
            echo -e "${GREEN}SSL certificates installed successfully!${NC}"
        else
            echo -e "${RED}Failed to generate SSL certificates. Check:${NC}"
            echo -e "${RED}1. Port 80 is open in security group${NC}"
            echo -e "${RED}2. Domain test.theairco.ai points to this server IP${NC}"
            exit 1
        fi
    fi
fi

# Pull latest code from GitHub
echo -e "${YELLOW}Pulling latest code from GitHub...${NC}"
git pull origin clean-main

# Start services
echo -e "${YELLOW}Building and starting services...${NC}"
docker-compose -f docker-compose.yml -f docker-compose.ec2.yml down 2>/dev/null || true
docker-compose -f docker-compose.yml -f docker-compose.ec2.yml up -d --build

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to become healthy...${NC}"
sleep 10

# Check health
HEALTH_STATUS=$(curl -sf http://localhost:8000/health -w "%{http_code}" -o /dev/null 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" == "200" ]; then
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}Deployment Successful!${NC}"
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}Website: https://test.theairco.ai${NC}"
    echo -e "${GREEN}Health Check: https://test.theairco.ai/health${NC}"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo -e "  View logs: ${NC}docker compose logs -f"
    echo -e "  Stop services: ${NC}docker compose down"
    echo -e "  Restart: ${NC}docker compose restart"
else
    echo -e "${YELLOW}Services starting... checking again in 30 seconds...${NC}"
    sleep 30
    HEALTH_STATUS=$(curl -sf http://localhost:8000/health -w "%{http_code}" -o /dev/null 2>/dev/null || echo "000")
    
    if [ "$HEALTH_STATUS" == "200" ]; then
        echo -e "${GREEN}Deployment Successful!${NC}"
        echo -e "${GREEN}Website: https://test.theairco.ai${NC}"
    else
        echo -e "${RED}Health check failed. Checking logs...${NC}"
        docker compose logs --tail=50 backend
        exit 1
    fi
fi
