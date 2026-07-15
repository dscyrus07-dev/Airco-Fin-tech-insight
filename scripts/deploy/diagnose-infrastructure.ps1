# Infrastructure Diagnostic Script for Airco Insights
# Run this to verify all services are properly configured

Write-Host "=== Airco Insights Infrastructure Diagnostics ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker is running" -ForegroundColor Green
    } else {
        Write-Host "❌ Docker is not running" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Docker is not installed or not running" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Checking Running Containers ===" -ForegroundColor Cyan
$containers = docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>&1
Write-Host $containers

Write-Host ""
Write-Host "=== Backend Environment Variables ===" -ForegroundColor Cyan
docker exec aircoinsightsfintech-backend-1 env | Select-String "MINIO|RABBITMQ|DATABASE|S3" | Sort-Object

Write-Host ""
Write-Host "=== MinIO Container Environment ===" -ForegroundColor Cyan
docker exec airco_minio env 2>&1 | Select-String "MINIO"

Write-Host ""
Write-Host "=== Testing MinIO Connectivity from Backend ===" -ForegroundColor Cyan
docker exec -it aircoinsightsfintech-backend-1 python3 -c "
import os
import sys

print('Environment variables:')
print(f'  MINIO_ENDPOINT: {os.getenv(\"MINIO_ENDPOINT\", \"NOT SET\")}')
print(f'  MINIO_ACCESS_KEY: {os.getenv(\"MINIO_ACCESS_KEY\", \"NOT SET\")}')
print(f'  MINIO_SECRET_KEY: {\"***\" if os.getenv(\"MINIO_SECRET_KEY\") else \"NOT SET\"}')
print()

try:
    import boto3
    from botocore.client import Config as BotoConfig
    
    endpoint = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
    access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    
    client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(signature_version='s3v4'),
        region_name='us-east-1',
    )
    
    buckets = client.list_buckets()
    print('✅ MinIO connection successful!')
    print(f'   Available buckets: {[b[\"Name\"] for b in buckets[\"Buckets\"]]}')
except Exception as e:
    print(f'❌ MinIO connection failed: {e}')
    sys.exit(1)
"

Write-Host ""
Write-Host "=== Checking MinIO Logs ===" -ForegroundColor Cyan
docker logs airco_minio --tail 20 2>&1

Write-Host ""
Write-Host "=== RabbitMQ Connection Test ===" -ForegroundColor Cyan
docker exec -it aircoinsightsfintech-backend-1 python3 -c "
import os
print(f'RABBITMQ_URL: {os.getenv(\"RABBITMQ_URL\", \"NOT SET\")}')
"

Write-Host ""
Write-Host "=== Database Connection Test ===" -ForegroundColor Cyan
docker exec -it aircoinsightsfintech-backend-1 python3 -c "
import os
import sys

db_url = os.getenv('DATABASE_URL', 'NOT SET')
if db_url == 'NOT SET':
    print('❌ DATABASE_URL not set')
    sys.exit(1)

# Mask password for display
import re
masked = re.sub(r':([^@]+)@', ':****@', db_url)
print(f'DATABASE_URL: {masked}')

try:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        print(f'✅ Database connection successful')
        print(f'   PostgreSQL version: {version}')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

Write-Host ""
Write-Host "=== Service Health Checks ===" -ForegroundColor Cyan
$services = @(
    @{Name="Backend"; Url="http://localhost:8000/health"},
    @{Name="Auth Service"; Url="http://localhost:8001/health"},
    @{Name="File Service"; Url="http://localhost:8002/health"},
    @{Name="PDF Service"; Url="http://localhost:8003/health"}
)

foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri $service.Url -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ $($service.Name) is healthy" -ForegroundColor Green
        } else {
            Write-Host "⚠️  $($service.Name) returned status $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ $($service.Name) is not responding" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Diagnostics Complete ===" -ForegroundColor Cyan
