#!/bin/bash

# Test Login Flow Script
# This script tests the Keycloak login flow with the test user

set -euo pipefail

echo "Testing Keycloak Login Flow..."
echo "================================"

# Configuration
API_URL="https://ec2-13-127-21-44.ap-south-1.compute.amazonaws.com"
TEST_EMAIL="test@airco.com"
TEST_PASSWORD="Test123!"

echo "API URL: $API_URL"
echo "Test Email: $TEST_EMAIL"
echo ""

# Test 1: Check if auth service is healthy
echo "1. Checking auth service health..."
if curl -s "$API_URL/api/auth/health" > /dev/null; then
    echo "   Auth service is healthy"
else
    echo "   Auth service is not responding"
    exit 1
fi

# Test 2: Attempt login with test credentials
echo "2. Testing login with test credentials..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo "   Login successful!"
    echo "   Access token received"
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token')
    
    # Test 3: Verify the token
    echo "3. Verifying access token..."
    VERIFY_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/verify-token" \
        -H "Authorization: Bearer $ACCESS_TOKEN")
    
    if echo "$VERIFY_RESPONSE" | jq -e '.valid' > /dev/null 2>&1; then
        echo "   Token verification successful!"
        USER_EMAIL=$(echo "$VERIFY_RESPONSE" | jq -r '.user.email')
        echo "   Authenticated as: $USER_EMAIL"
        echo ""
        echo "SUCCESS: Login flow is working correctly!"
        echo "401 Unauthorized error should be resolved."
    else
        echo "   Token verification failed"
        echo "   Response: $VERIFY_RESPONSE"
        exit 1
    fi
else
    echo "   Login failed!"
    echo "   Response: $LOGIN_RESPONSE"
    echo ""
    echo "TROUBLESHOOTING:"
    echo "1. Ensure Keycloak setup script was run on EC2"
    echo "2. Check that auth service was restarted"
    echo "3. Verify environment variables are updated"
    echo "4. Check Keycloak admin console at: $API_URL/admin"
    exit 1
fi

echo ""
echo "Test completed successfully!"
