#!/bin/bash
# Quick Update Script - Pull latest code and redeploy
# Run this on EC2 to update the deployment

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/opt/airco"

echo -e "${YELLOW}Updating Airco Insights from GitHub...${NC}"

# Navigate to project directory
cd ${PROJECT_DIR}

# Pull latest changes
echo -e "${YELLOW}Pulling latest code...${NC}"
git pull origin clean-main

# Rebuild and restart services
echo -e "${YELLOW}Rebuilding and restarting services...${NC}"
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.ec2.yml up -d --build

# Wait and check health
echo -e "${YELLOW}Checking deployment health...${NC}"
sleep 10

HEALTH_STATUS=$(curl -sf http://localhost:8000/health -w "%{http_code}" -o /dev/null 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" == "200" ]; then
    echo -e "${GREEN}Update successful!${NC}"
    echo -e "${GREEN}Website: https://test.theairco.ai${NC}"
else
    echo -e "${YELLOW}Services still starting... checking again...${NC}"
    sleep 20
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}Update successful!${NC}"
    else
        echo -e "Update completed but health check failed. Check logs: docker-compose logs -f"
    fi
fi
