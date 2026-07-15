Airco Insights FinTech - Security & Code Audit Report
Date: June 14, 2026
Scope: Full codebase (backend, frontend, microservices, infrastructure, dependencies)

Executive Summary
Critical Issues: 7
High Issues: 8
Medium Issues: 6
Low Issues: 4
Total: 25

Top 5 Critical Issues (Fix Immediately)
HIGH CVE-2024-53981 - python-multipart 0.0.6 vulnerable to DoS attack
Keycloak client secret blank in docker-compose for auth-service - login broken
CORS wildcard on all microservices - allows any origin
Supabase credentials exposed in .env file
Backend runs as root in Docker container
🔴 Critical Issues
1. HIGH CVE-2024-53981 - python-multipart DoS Vulnerability
Severity: CRITICAL
CVSS: 7.5 (HIGH)
Affected Files: All requirements.txt files (backend + all services)

Issue: All services use python-multipart==0.0.6 which contains a denial-of-service vulnerability (CVE-2024-53981). When parsing multipart form data, the parser can stall the event loop in ASGI applications.

Impact: Attacker can send malformed multipart requests to crash the server or cause DoS.

Fix: Upgrade to python-multipart>=0.0.18 in all requirements.txt files.

2. Keycloak Client Secret Blank in docker-compose
Severity: CRITICAL
File: [x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:18](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:17:0-17:999)

Issue: The auth-service has an empty KEYCLOAK_CLIENT_SECRET:



yaml
KEYCLOAK_CLIENT_SECRET:   
Impact: Token exchange (/auth/callback) will fail because Keycloak rejects the wrong secret. Login is broken.

Fix:



yaml
KEYCLOAK_CLIENT_SECRET: ${KEYCLOAK_CLIENT_SECRET:-airco-frontend-secret-2024-secure-key-abc123xyz}
3. CORS Wildcard on All Microservices
Severity: CRITICAL
Files: main.py, main.py, main.py, main.py

Issue: All microservices have allow_origins=["*"]:



python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Impact: Any website can make authenticated requests to your microservices. This completely bypasses CORS protection.

Fix: Use environment variable with whitelist:



python
from .config import settings
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, ...)
4. Supabase Credentials Exposed in .env
Severity: CRITICAL
File: .env:33

Issue: Production Supabase connection string with credentials is in .env:



env
DATABASE_URL=postgresql://postgres.zesqwvycakqrrtdunzlt:4IBNX7HW0Ynz6Ur6@aws-1-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
Impact: If .env is committed to git (it's not in .gitignore but could be accidentally committed), credentials are exposed.

Fix:

Rotate the Supabase password immediately
Use separate .env.local for local development
Never commit production credentials to any file
5. Backend Docker Container Runs as Root
Severity: CRITICAL
File: Dockerfile

Issue: Backend container has no user switch - runs as root.

Impact: If the container is compromised, attacker has root access to the host filesystem.

Fix: Add non-root user (see auth-service Dockerfile for reference):



dockerfile
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app
6. Keycloak URL Hardcoded in auth-service docker-compose
Severity: CRITICAL
File: [x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:14](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:13:0-13:999)

Issue: KEYCLOAK_URL is hardcoded to http://localhost:8080.

Impact: On EC2 or any non-localhost deployment, token issuer validation will fail.

Fix:



yaml
KEYCLOAK_URL: ${KEYCLOAK_URL:-http://localhost:8080}
7. local.env Not Covered by .gitignore
Severity: CRITICAL
File: .gitignore

Issue: .gitignore only covers .env and .env.local but not local.env.

Impact: local.env (which contains production Supabase credentials) could be accidentally committed to git.

Fix: Add to .gitignore:



gitignore
local.env
🟠 High Issues
8. Next.js 16 with React 18 - Version Mismatch
Severity: HIGH
File: package.json

Issue: Using Next.js 16.2.4 with React 18.3.1. Next.js 16 expects React 19+.

Fix: Upgrade to React 19:



json
"react": "^19.0.0",
"react-dom": "^19.0.0"
9. Dead Code with Hook Misuse - lib/api.ts
Severity: HIGH
File: api.ts

Issue: The file contains useAuth() hook called from a plain async function (lines 9-10). This throws "Invalid hook call" if ever used. Currently it's dead code (not imported anywhere).

Fix: Delete the file (it's unused) or fix by reading from sessionStorage directly.

10. Auth Service Dockerfile Healthcheck Fails
Severity: HIGH
File: [x:/FinTech SAAS/Airco Insights Fintech/services/auth-service/Dockerfile:28-29](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/services/auth-service/Dockerfile:27:0-28:999)

Issue: Healthcheck uses requests library which isn't installed.

Fix: Use urllib (built-in):



dockerfile
CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"
11. KC_SPI Invalid Environment Variable
Severity: HIGH
File: [x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:286](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:285:0-285:999)

Issue: KC_SPI is not a valid Keycloak environment variable.

Fix: Remove the line.

12. Keycloak Image Pinned to latest
Severity: HIGH
File: [x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:256](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:255:0-255:999)

Issue: Keycloak uses latest tag.

Fix: Pin to specific version:



yaml
image: quay.io/keycloak/keycloak:26.2
13. NEXT_PUBLIC_* Runtime Env Vars are Dead Code
Severity: HIGH
File: [x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:224-231](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/infra/docker/docker-compose.yml:223:0-230:999)

Issue: NEXT_PUBLIC_* variables are set as runtime environment variables but they are baked into the Next.js bundle at build time.

Fix: Remove the NEXT_PUBLIC_* lines from the environment: block. Only the build args: matter.

14. Default Password Placeholders in .env
Severity: HIGH
File: .env

Issue: Multiple placeholders not replaced: change-me-keycloak-admin, change-me-jwt-secret, REPLACE_ME for API keys.

Fix: Replace all placeholders with production values before deployment.

15. AuthMiddleware Mutates Request Headers Directly
Severity: HIGH
File: [x:/FinTech SAAS/Airco Insights Fintech/backend/app/middleware/auth_middleware.py:79-95](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/backend/app/middleware/auth_middleware.py:78:0-94:999)

Issue: Direct mutation of request.headers.__dict__["_list"] is fragile and may break with future Starlette/FastAPI updates.

Fix: Use Starlette's Request.scope to set headers properly.

🟡 Medium Issues
16. pandas 3.0 Breaking Changes
Severity: MEDIUM
File: [x:/FinTech SAAS/Airco Insights Fintech/backend/requirements.txt:16](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/backend/requirements.txt:15:0-15:999)

Issue: pandas==3.0.2 introduces Copy-on-Write as default, which may break existing code that expects in-place mutation.

Fix: Review all pandas usage for in-place mutations.

17. RabbitMQ Default Credentials
Severity: MEDIUM
File: .env:43-44

Issue: Using default RabbitMQ credentials (guest/guest).

Fix: Change to strong random credentials.

18. MinIO Default Credentials
Severity: MEDIUM
File: .env:37-41

Issue: Using default MinIO credentials (minioadmin/minioadmin).

Fix: Change to strong random credentials.

19. No Keycloak Realm Import File
Severity: MEDIUM

Issue: The frontend-app Keycloak client was manually created via kcadm.sh. No realm import file exists.

Fix: Export the realm and mount it as an import in docker-compose.

20. No Rate Limiting on Upload Endpoint
Severity: MEDIUM
File: upload_async.py

Issue: The /upload/bank-statement-async endpoint has no rate limiting.

Fix: Add rate limiting using slowapi or similar.

21. No Input Validation on bank_name Parameter
Severity: MEDIUM
File: [x:/FinTech SAAS/Airco Insights Fintech/backend/app/api/routes/upload_async.py:152](cci:4://file://x:/FinTech SAAS/Airco Insights Fintech/backend/app/api/routes/upload_async.py:151:0-151:999)

Issue: bank_name is accepted as-is without validation against known banks.

Fix: Validate against a whitelist of supported banks.

🟢 Low Issues
22. No Automated Security Scanning
Severity: LOW

Issue: No GitHub Actions or CI pipeline for automated security scanning.

Fix: Add Dependabot and Snyk to CI pipeline.

23. No Database Migration Rollback Strategy
Severity: LOW

Issue: Alembic migrations exist but no documented rollback strategy.

Fix: Document rollback procedures and test them.

24. No Centralized Error Handling
Severity: LOW

Issue: Error handling is scattered across endpoints with inconsistent error responses.

Fix: Implement a global exception handler.

25. No API Documentation
Severity: LOW

Issue: No OpenAPI/Swagger documentation beyond FastAPI's auto-generated docs.

Fix: Add comprehensive API documentation with examples.

Recommended Action Plan
Immediate (Within 24 Hours)
Upgrade python-multipart to >=0.0.18 in all requirements.txt files
Fix KEYCLOAK_CLIENT_SECRET in docker-compose.yml
Fix CORS on all microservices
Rotate Supabase credentials
Add local.env to .gitignore
Short Term (Within 1 Week)
Fix backend Dockerfile to run as non-root
Fix KEYCLOAK_URL to use env var in docker-compose
Upgrade React to 19 for Next.js 16 compatibility
Remove or fix api.ts dead code
Fix auth-service Dockerfile healthcheck
Pin Keycloak image version
Remove invalid KC_SPI env var
Remove dead NEXT_PUBLIC_* runtime env vars
Replace all password placeholders in .env
Fix AuthMiddleware header mutation
Medium Term (Within 1 Month)
Review pandas 3.0 breaking changes
Change RabbitMQ and MinIO default credentials
Add Keycloak realm import file
Add rate limiting to upload endpoint
Add bank_name validation
Long Term (Ongoing)
Add automated security scanning
Document database migration rollback
Implement centralized error handling
Add comprehensive API documentation
Conclusion
The codebase has several critical security vulnerabilities that must be addressed immediately, particularly the CVE in python-multipart and the exposed credentials. The microservices architecture is well-designed but needs hardening around CORS and authentication. The frontend is mostly clean but has a version mismatch with Next.js 16.

Overall Risk Level: HIGH

Recommended: Address all Critical and High issues before deploying to production.*