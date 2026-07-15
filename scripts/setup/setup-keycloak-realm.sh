#!/bin/bash
# Setup Keycloak Realm and Client for Airco Insights

set -e

KEYCLOAK_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
REALM="airco-insights"
CLIENT_ID="frontend-app"

# Wait for Keycloak to be ready
echo "Waiting for Keycloak to be ready..."
for i in {1..30}; do
    if curl -sf "${KEYCLOAK_URL}/realms/master" > /dev/null 2>&1; then
        echo "Keycloak is ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 5
done

# Get admin token
echo "Getting admin token..."
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

echo "Admin token acquired"

# Create realm if not exists
echo "Creating realm: ${REALM}..."
curl -s -X POST "${KEYCLOAK_URL}/admin/realms" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"realm\": \"${REALM}\",
        \"enabled\": true,
        \"displayName\": \"Airco Insights\",
        \"displayNameHtml\": \"<div class='kc-logo-text'>Airco Insights</div>\",
        \"sslRequired\": \"external\",
        \"registrationAllowed\": false,
        \"loginWithEmailAllowed\": true,
        \"duplicateEmailsAllowed\": false,
        \"resetPasswordAllowed\": true,
        \"editUsernameAllowed\": false,
        \"bruteForceProtected\": true,
        \"permanentLockout\": false,
        \"maxFailureWaitSeconds\": 900,
        \"minimumQuickLoginWaitSeconds\": 60,
        \"waitIncrementSeconds\": 60,
        \"quickLoginCheckMilliSeconds\": 1000,
        \"maxDeltaTimeSeconds\": 43200,
        \"failureFactor\": 30,
        \"defaultSignatureAlgorithm\": \"RS256\",
        \"revokeRefreshToken\": false,
        \"refreshTokenMaxReuse\": 0,
        \"accessTokenLifespan\": 300,
        \"accessTokenLifespanForImplicitFlow\": 900,
        \"ssoSessionIdleTimeout\": 1800,
        \"ssoSessionMaxLifespan\": 36000,
        \"ssoSessionIdleTimeoutRememberMe\": 0,
        \"ssoSessionMaxLifespanRememberMe\": 0,
        \"offlineSessionIdleTimeout\": 2592000,
        \"offlineSessionMaxLifespanEnabled\": false,
        \"offlineSessionMaxLifespan\": 5184000,
        \"clientSessionIdleTimeout\": 0,
        \"clientSessionMaxLifespan\": 0,
        \"clientOfflineSessionIdleTimeout\": 0,
        \"clientOfflineSessionMaxLifespan\": 0,
        \"accessCodeLifespan\": 60,
        \"accessCodeLifespanUserAction\": 300,
        \"accessCodeLifespanLogin\": 1800,
        \"actionTokenGeneratedByAdminLifespan\": 43200,
        \"actionTokenGeneratedByUserLifespan\": 300
    }" || echo "Realm may already exist"

# Create client
echo "Creating client: ${CLIENT_ID}..."
curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/clients" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"clientId\": \"${CLIENT_ID}\",
        \"name\": \"Frontend Application\",
        \"description\": \"Airco Insights Frontend\",
        \"enabled\": true,
        \"clientAuthenticatorType\": \"client-secret\",
        \"secret\": \"airco-frontend-secret-2024-secure-key-abc123xyz\",
        \"redirectUris\": [
            \"https://test.theairco.ai/*\",
            \"https://test.theairco.ai\",
            \"http://localhost:3000/*\",
            \"http://localhost:3000\"
        ],
        \"webOrigins\": [
            \"https://test.theairco.ai\",
            \"http://localhost:3000\"
        ],
        \"notBefore\": 0,
        \"bearerOnly\": false,
        \"consentRequired\": false,
        \"standardFlowEnabled\": true,
        \"implicitFlowEnabled\": false,
        \"directAccessGrantsEnabled\": true,
        \"serviceAccountsEnabled\": false,
        \"publicClient\": false,
        \"frontchannelLogout\": true,
        \"protocol\": \"openid-connect\",
        \"attributes\": {
            \"oidc.ciba.grant.enabled\": \"false\",
            \"client.secret.creation.time\": \"1724601200\",
            \"backchannel.logout.session.required\": \"true\",
            \"oauth2.device.authorization.grant.enabled\": \"false\",
            \"display.on.consent.screen\": \"false\",
            \"backchannel.logout.revoke.offline.tokens\": \"false\"
        },
        \"authenticationFlowBindingOverrides\": {},
        \"fullScopeAllowed\": true,
        \"nodeReRegistrationTimeout\": -1,
        \"protocolMappers\": [
            {
                \"name\": \"email\",
                \"protocol\": \"openid-connect\",
                \"protocolMapper\": \"oidc-usermodel-property-mapper\",
                \"consentRequired\": false,
                \"config\": {
                    \"userinfo.token.claim\": \"true\",
                    \"user.attribute\": \"email\",
                    \"id.token.claim\": \"true\",
                    \"access.token.claim\": \"true\",
                    \"claim.name\": \"email\",
                    \"jsonType.label\": \"String\"
                }
            },
            {
                \"name\": \"username\",
                \"protocol\": \"openid-connect\",
                \"protocolMapper\": \"oidc-usermodel-property-mapper\",
                \"consentRequired\": false,
                \"config\": {
                    \"userinfo.token.claim\": \"true\",
                    \"user.attribute\": \"username\",
                    \"id.token.claim\": \"true\",
                    \"access.token.claim\": \"true\",
                    \"claim.name\": \"preferred_username\",
                    \"jsonType.label\": \"String\"
                }
            }
        ],
        \"defaultClientScopes\": [
            \"web-origins\",
            \"acr\",
            \"roles\",
            \"profile\",
            \"email\"
        ],
        \"optionalClientScopes\": [
            \"offline_access\",
            \"microprofile-jwt\"
        ]
    }" || echo "Client may already exist"

# Create a test user
echo "Creating test user..."
USER_ID=$(curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/users" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"username\": \"test@airco.com\",
        \"email\": \"test@airco.com\",
        \"enabled\": true,
        \"emailVerified\": true,
        \"firstName\": \"Test\",
        \"lastName\": \"User\",
        \"credentials\": [
            {
                \"type\": \"password\",
                \"value\": \"Test123!\",
                \"temporary\": false
            }
        ]
    }" -v 2>&1 | grep -i "location" | cut -d'/' -f8 | tr -d '\r')

if [ -n "$USER_ID" ]; then
    echo "Test user created: test@airco.com / Test123!"
else
    echo "Test user may already exist"
fi

echo ""
echo "=========================================="
echo "Keycloak Setup Complete!"
echo "=========================================="
echo "Realm: ${REALM}"
echo "Client: ${CLIENT_ID}"
echo "Admin URL: https://test.theairco.ai/admin"
echo "Admin User: admin"
echo "Test User: test@airco.com / Test123!"
echo "=========================================="
