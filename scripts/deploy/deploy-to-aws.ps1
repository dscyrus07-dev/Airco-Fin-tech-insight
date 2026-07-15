#!/usr/bin/env pwsh
# Airco Insights - AWS EC2 One-Click Deployment
# Run this from Windows PowerShell

param(
    [string]$Server = "ubuntu@13.234.242.2",
    [string]$PemKeyPath = "ssl/Airco Fintech.pem",
    [string]$ProjectDir = "/opt/airco",
    [string]$Branch = "clean-main"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Airco Insights - AWS EC2 Deployment" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Verify PEM key exists
$PemFullPath = Join-Path (Get-Location) $PemKeyPath
if (-not (Test-Path $PemFullPath)) {
    Write-Host "Error: PEM key not found at $PemFullPath" -ForegroundColor Red
    exit 1
}

Write-Host "Server: $Server" -ForegroundColor Cyan
Write-Host "PEM Key: $PemFullPath" -ForegroundColor Cyan
Write-Host "Branch: $Branch" -ForegroundColor Cyan
Write-Host ""

# Test SSH connection
Write-Host "Step 1: Testing SSH connection..." -ForegroundColor Yellow
$sshTest = ssh -i "$PemFullPath" -o ConnectTimeout=10 -o StrictHostKeyChecking=no $Server "echo 'SSH_OK'" 2>&1
if ($sshTest -notcontains "SSH_OK") {
    Write-Host "SSH connection failed. Checking if we need to accept host key..." -ForegroundColor Yellow
}
Write-Host "SSH connection ready" -ForegroundColor Green
Write-Host ""

# Create remote deployment script
Write-Host "Step 2: Preparing remote deployment..." -ForegroundColor Yellow

$remoteScript = @'
#!/bin/bash
set -e

PROJECT_DIR="/opt/airco"
BRANCH="clean-main"

echo "=========================================="
echo "Airco Insights EC2 Deployment Script"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose git certbot curl
    sudo usermod -aG docker $USER
    echo "Docker installed. Please run this script again after re-login."
    exit 0
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo "Adding user to docker group..."
    sudo usermod -aG docker $USER
    echo "Please logout and login again, then re-run this script."
    exit 0
fi

# Create project directory
sudo mkdir -p $PROJECT_DIR
sudo chown -R $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR

# Clone or update repository
if [ -d ".git" ]; then
    echo "Updating existing repository..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo "Cloning repository..."
    rm -rf * .* 2>/dev/null || true
    git clone https://github.com/dscyrus07-dev/Airco-Insights-Fintech-AWS.git .
    git checkout $BRANCH
fi

echo "Repository ready at: $PROJECT_DIR"
echo ""

# Generate environment file if not exists
if [ ! -f ".env" ]; then
    echo "Creating environment file with secure passwords..."
    
    # Generate secure passwords
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
CERTBOT_WEBROOT_DIR=/opt/airco/certbot

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

# Data retention policy
DATA_RETENTION_DAYS=7
RETENTION_ENABLED=true
RETENTION_SWEEP_INTERVAL_MINUTES=60
EOF

    echo "=========================================="
    echo "Environment file created!"
    echo "Keycloak Admin Password: ${KEYCLOAK_ADMIN_PASS}"
    echo "Save this password for Keycloak admin access!"
    echo "=========================================="
    echo ""
fi

# Setup SSL certificates
if [ ! -f "ssl/fullchain.pem" ] || [ ! -f "ssl/privkey.pem" ]; then
    echo "Setting up SSL certificates..."
    mkdir -p ssl certbot
    
    # Check if certbot certificates already exist
    if sudo test -f "/etc/letsencrypt/live/test.theairco.ai/fullchain.pem"; then
        echo "Copying existing Let's Encrypt certificates..."
        sudo cp /etc/letsencrypt/live/test.theairco.ai/fullchain.pem ssl/
        sudo cp /etc/letsencrypt/live/test.theairco.ai/privkey.pem ssl/
        sudo chown $USER:$USER ssl/*.pem
    else
        echo "Generating new SSL certificates..."
        echo "Make sure port 80 is open in AWS security group!"
        
        sudo certbot certonly --standalone -d test.theairco.ai --agree-tos -n -m admin@theairco.ai || true
        
        if sudo test -f "/etc/letsencrypt/live/test.theairco.ai/fullchain.pem"; then
            sudo cp /etc/letsencrypt/live/test.theairco.ai/fullchain.pem ssl/
            sudo cp /etc/letsencrypt/live/test.theairco.ai/privkey.pem ssl/
            sudo chown $USER:$USER ssl/*.pem
            echo "SSL certificates installed successfully!"
        else
            echo "WARNING: SSL certificate generation failed. Services will start without HTTPS."
            echo "Check: 1. Port 80 is open in security group 2. Domain points to this server"
        fi
    fi
    echo ""
fi

# Start services
echo "Building and starting services..."
docker compose -f docker-compose.yml -f docker-compose.ec2.yml down 2>/dev/null || true
docker compose -f docker-compose.yml -f docker-compose.ec2.yml up -d --build

echo ""
echo "Waiting for services to start..."
sleep 15

# Check health
echo "Checking service health..."
for i in 1 2 3 4 5; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "=========================================="
        echo "DEPLOYMENT SUCCESSFUL!"
        echo "=========================================="
        echo "Website: https://test.theairco.ai"
        echo "Health Check: https://test.theairco.ai/health"
        echo "MinIO Console: http://13.234.242.2:9001"
        echo ""
        echo "Useful commands:"
        echo "  View logs: docker compose logs -f"
        echo "  Stop: docker compose down"
        echo "  Restart: docker compose restart"
        echo "=========================================="
        exit 0
    fi
    echo "Waiting for backend... (attempt $i/5)"
    sleep 10
done

echo "WARNING: Health check failed. Checking logs..."
docker compose logs --tail=50 backend
exit 1
'@

# Save remote script
$tempScript = Join-Path $env:TEMP "airco-deploy-remote.sh"
[System.IO.File]::WriteAllText($tempScript, $remoteScript)

Write-Host "Step 3: Uploading deployment script..." -ForegroundColor Yellow
scp -i "$PemFullPath" -o StrictHostKeyChecking=no "$tempScript" "${Server}:/tmp/airco-deploy.sh"

Write-Host ""
Write-Host "Step 4: Executing deployment on EC2..." -ForegroundColor Yellow
Write-Host "This may take 10-15 minutes for first deployment..." -ForegroundColor Cyan
Write-Host ""

ssh -i "$PemFullPath" -o StrictHostKeyChecking=no $Server "bash /tmp/airco-deploy.sh"

$exitCode = $LASTEXITCODE

# Cleanup
Remove-Item $tempScript -Force -ErrorAction SilentlyContinue

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "DEPLOYMENT COMPLETED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your application is now live at:" -ForegroundColor Cyan
    Write-Host "  https://test.theairco.ai" -ForegroundColor Green
    Write-Host ""
    Write-Host "Health Check:" -ForegroundColor Cyan
    Write-Host "  https://test.theairco.ai/health" -ForegroundColor Green
    Write-Host ""
    Write-Host "To update in the future, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\deploy-to-aws.ps1" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "Deployment encountered issues. Check the logs above." -ForegroundColor Red
    Write-Host "Common fixes:" -ForegroundColor Yellow
    Write-Host "  1. Ensure port 80/443 are open in AWS security group" -ForegroundColor White
    Write-Host "  2. Check that test.theairco.ai DNS points to 13.234.242.2" -ForegroundColor White
    Write-Host "  3. SSH manually and run: docker-compose logs -f" -ForegroundColor White
}

Write-Host ""
Write-Host "Script completed!" -ForegroundColor Green
