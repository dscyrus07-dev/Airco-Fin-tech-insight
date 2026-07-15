#!/bin/bash
# Fix Keycloak Client Redirect URIs

KEYCLOAK_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
REALM="airco-insights"
CLIENT_ID="frontend-app"

# Get admin token
ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${ADMIN_USER}" \
    -d "password=${ADMIN_PASS}" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$ADMIN_TOKEN" ]; then
    echo "Failed to get admin token"
    exit 1
fi

# Get client internal ID
CLIENT_UUID=$(curl -s "${KEYCLOAK_URL}/admin/realms/${REALM}/clients" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$CLIENT_UUID" ]; then
    echo "Failed to get client UUID"
    exit 1
fi

echo "Client UUID: $CLIENT_UUID"

# Get current client config
curl -s "${KEYCLOAK_URL}/admin/realms/${REALM}/clients/${CLIENT_UUID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" > /tmp/client-config.json

# Update redirect URIs
curl -s -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM}/clients/${CLIENT_UUID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "redirectUris": [
            "https://test.theairco.ai/*",
            "https://test.theairco.ai",
            "http://localhost:3000/*",
            "http://localhost:3000",
            "http://localhost:8080/*",
            "http://13.234.242.2:3000/*",
            "https://13.234.242.2/*"
        ],
        "webOrigins": [
            "https://test.theairco.ai",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://13.234.242.2:3000",
            "https://13.234.242.2",
            "+"
        ]
    }'

echo ""
echo "Client redirect URIs updated successfully!"
echo ""
echo "Valid redirect URIs:"
echo "  - https://test.theairco.ai/*"
echo "  - http://localhost:3000/*"
echo "  - http://localhost:8080/*"
