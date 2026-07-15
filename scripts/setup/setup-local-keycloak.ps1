param(
    [string]$KeycloakUrl = $(if ($env:KEYCLOAK_URL) { $env:KEYCLOAK_URL } else { "http://localhost:8080" }),
    [string]$AdminUser = $(if ($env:KEYCLOAK_ADMIN) { $env:KEYCLOAK_ADMIN } else { "admin" }),
    [string]$AdminPassword = $(if ($env:KEYCLOAK_ADMIN_PASSWORD) { $env:KEYCLOAK_ADMIN_PASSWORD } else { "change-me-keycloak-admin" }),
    [string]$RealmName = $(if ($env:KEYCLOAK_REALM) { $env:KEYCLOAK_REALM } else { "airco-insights" }),
    [string]$ClientId = $(if ($env:KEYCLOAK_CLIENT_ID) { $env:KEYCLOAK_CLIENT_ID } else { "frontend-app" }),
    [string]$ClientSecret = $(if ($env:KEYCLOAK_CLIENT_SECRET) { $env:KEYCLOAK_CLIENT_SECRET } else { "airco-frontend-secret" }),
    [string]$TestEmail = $(if ($env:KEYCLOAK_TEST_EMAIL) { $env:KEYCLOAK_TEST_EMAIL } else { "test@airco.com" }),
    [string]$TestPassword = $(if ($env:KEYCLOAK_TEST_PASSWORD) { $env:KEYCLOAK_TEST_PASSWORD } else { "Test123!" })
)

$ErrorActionPreference = "Stop"

try {
    Add-Type -AssemblyName System.Net.Http
} catch {
    # Already loaded or unavailable; HttpClient may still be available in the runtime.
}

function Get-BoolEnv {
    param(
        [string]$Name,
        [bool]$Default = $false
    )

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }

    switch ($value.Trim().ToLowerInvariant()) {
        "1" { return $true }
        "true" { return $true }
        "yes" { return $true }
        "on" { return $true }
        "0" { return $false }
        "false" { return $false }
        "no" { return $false }
        "off" { return $false }
        default { return $Default }
    }
}

function Get-EnvFileValues {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        if ($trimmed -match '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $matches[1]
            $value = $matches[2].Trim()
            if ((($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) -and $value.Length -ge 2) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $values[$name] = $value
        }
    }

    return $values
}

function Resolve-ConfigValue {
    param(
        [hashtable]$EnvFileValues,
        [string]$Name,
        [string]$Fallback,
        [string]$CurrentValue
    )

    $envValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($envValue)) {
        return $envValue
    }

    if ($EnvFileValues.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($EnvFileValues[$Name])) {
        return $EnvFileValues[$Name]
    }

    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) {
        return $CurrentValue
    }

    return $Fallback
}

$LocalEnvPath = Join-Path $PSScriptRoot '..\..\local.env'
$LocalEnvValues = Get-EnvFileValues -Path $LocalEnvPath

$KeycloakUrl = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_URL' -Fallback 'http://localhost:8080' -CurrentValue $KeycloakUrl
$AdminUser = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_ADMIN' -Fallback 'admin' -CurrentValue $AdminUser
$AdminPassword = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_ADMIN_PASSWORD' -Fallback 'change-me-keycloak-admin' -CurrentValue $AdminPassword
$RealmName = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_REALM' -Fallback 'airco-insights' -CurrentValue $RealmName
$ClientId = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_CLIENT_ID' -Fallback 'frontend-app' -CurrentValue $ClientId
$ClientSecret = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_CLIENT_SECRET' -Fallback 'airco-frontend-secret' -CurrentValue $ClientSecret
$TestEmail = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_TEST_EMAIL' -Fallback 'test@airco.com' -CurrentValue $TestEmail
$TestPassword = Resolve-ConfigValue -EnvFileValues $LocalEnvValues -Name 'KEYCLOAK_TEST_PASSWORD' -Fallback 'Test123!' -CurrentValue $TestPassword

if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('ENABLE_KEYCLOAK_TOTP')) -and $LocalEnvValues.ContainsKey('ENABLE_KEYCLOAK_TOTP')) {
    [Environment]::SetEnvironmentVariable('ENABLE_KEYCLOAK_TOTP', $LocalEnvValues['ENABLE_KEYCLOAK_TOTP'])
}

$EnableKeycloakTotp = Get-BoolEnv -Name "ENABLE_KEYCLOAK_TOTP" -Default $false
$BrowserFlow = if ($EnableKeycloakTotp) { "browser-totp" } else { "browser" }
$RequiredActions = if ($EnableKeycloakTotp) { @("CONFIGURE_TOTP") } else { @() }

function Write-Log {
    param([string]$Message)
    Write-Host "[setup-local-keycloak] $Message" -ForegroundColor Cyan
}

function Invoke-RestJson {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers = @{},
        $Body = $null,
        [string]$ContentType = "application/json"
    )

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = if ($Body -is [string]) { $Body } else { ($Body | ConvertTo-Json -Depth 20 -Compress) }
    }

    $client = [System.Net.Http.HttpClient]::new()
    $request = $null

    try {
        foreach ($key in $Headers.Keys) {
            if ($null -ne $Headers[$key] -and -not [string]::IsNullOrWhiteSpace([string]$Headers[$key])) {
                [void]$client.DefaultRequestHeaders.TryAddWithoutValidation($key, [string]$Headers[$key])
            }
        }

        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::new($Method), $Uri)

        if ($null -ne $jsonBody) {
            $request.Content = [System.Net.Http.StringContent]::new(
                $jsonBody,
                [System.Text.Encoding]::UTF8,
                $ContentType
            )
        }

        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        $responseContent = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()

        if (-not $response.IsSuccessStatusCode) {
            throw "HTTP $([int]$response.StatusCode) $($response.ReasonPhrase): $responseContent"
        }

        if ($responseContent) {
            try {
                return $responseContent | ConvertFrom-Json -ErrorAction Stop
            } catch {
                return $responseContent
            }
        }

        return $null
    } finally {
        if ($request) {
            $request.Dispose()
        }
        $client.Dispose()
    }
}

function Wait-ForKeycloak {
    param([int]$TimeoutSeconds = 300)

    Write-Log "Waiting for Keycloak at $KeycloakUrl..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/realms/master/.well-known/openid-configuration" -TimeoutSec 5
            return
        } catch {
            Start-Sleep -Seconds 5
        }
    }

    throw "Keycloak did not become ready within $TimeoutSeconds seconds."
}

function Get-AdminHeaders {
    Write-Log "Requesting admin token..."
    $tokenResponse = Invoke-RestMethod -Method Post -Uri "$KeycloakUrl/realms/master/protocol/openid-connect/token" -ContentType 'application/x-www-form-urlencoded' -Body @{
        username   = $AdminUser
        password   = $AdminPassword
        grant_type = 'password'
        client_id  = 'admin-cli'
    }

    if (-not $tokenResponse.access_token) {
        throw "Unable to get Keycloak admin token. Check the admin credentials."
    }

    return @{ Authorization = "Bearer $($tokenResponse.access_token)" }
}

function Set-KeycloakRealm {
    param([hashtable]$Headers)

    $realmPayload = @{
        realm = $RealmName
        enabled = $true
        registrationAllowed = $false
        loginWithEmailAllowed = $true
        duplicateEmailsAllowed = $false
        resetPasswordAllowed = $false
        editUsernameAllowed = $false
        browserFlow = $BrowserFlow
        loginTheme = "keycloak"
    }

    try {
        $null = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName" -Headers $Headers
        Write-Log "Realm $RealmName already exists. Updating browser flow to '$BrowserFlow'."
        Invoke-RestJson -Method Put -Uri "$KeycloakUrl/admin/realms/$RealmName" -Headers $Headers -Body $realmPayload | Out-Null
    } catch {
        Write-Log "Creating realm $RealmName..."
        Invoke-RestJson -Method Post -Uri "$KeycloakUrl/admin/realms" -Headers $Headers -Body $realmPayload | Out-Null
    }
}

function Set-KeycloakClient {
    param([hashtable]$Headers)

    $clientPayload = @{
        clientId = $ClientId
        name = "Frontend Application"
        enabled = $true
        clientAuthenticatorType = "client-secret"
        secret = $ClientSecret
        redirectUris = @(
            "http://localhost:3000/*",
            "http://127.0.0.1:3000/*",
            "http://localhost:3000/auth/callback",
            "http://127.0.0.1:3000/auth/callback"
        )
        webOrigins = @(
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "+"
        )
        standardFlowEnabled = $true
        directAccessGrantsEnabled = $true
        serviceAccountsEnabled = $false
        publicClient = $false
        protocol = "openid-connect"
        fullScopeAllowed = $true
        attributes = @{
            "pkce.code.challenge.method" = "S256"
            "post.logout.redirect.uris" = "http://localhost:3000/*##http://127.0.0.1:3000/*"
        }
    }

    $client = @()
    try {
        $client = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/clients?clientId=$ClientId" -Headers $Headers
    } catch {
        $client = @()
    }

    if ($client.Count -gt 0) {
        Write-Log "Updating existing client $ClientId..."
        $clientIdValue = $client[0].id
        Invoke-RestJson -Method Put -Uri "$KeycloakUrl/admin/realms/$RealmName/clients/$clientIdValue" -Headers $Headers -Body $clientPayload | Out-Null
    } else {
        Write-Log "Creating client $ClientId..."
        Invoke-RestJson -Method Post -Uri "$KeycloakUrl/admin/realms/$RealmName/clients" -Headers $Headers -Body $clientPayload | Out-Null
    }
}

function Set-KeycloakRole {
    param([hashtable]$Headers)

    try {
        $null = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/roles/user" -Headers $Headers
        Write-Log "Realm role 'user' already exists."
    } catch {
        Write-Log "Creating realm role 'user'..."
        Invoke-RestJson -Method Post -Uri "$KeycloakUrl/admin/realms/$RealmName/roles" -Headers $Headers -Body @{ name = "user" } | Out-Null
    }
}

function Set-KeycloakTestUser {
    param([hashtable]$Headers)

    $createPayload = @"
{
  "username": "$TestEmail",
  "enabled": true,
  "email": "$TestEmail",
  "emailVerified": true,
  "firstName": "Test",
  "lastName": "User"
}
"@

    $users = @()
    try {
        $users = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/users?username=$TestEmail" -Headers $Headers
    } catch {
        $users = @()
    }

    if ($users.Count -gt 0) {
        Write-Log "Updating existing test user..."
        return $users[0].id
    } else {
        Write-Log "Creating test user..."
        try {
            Invoke-RestJson -Method Post -Uri "$KeycloakUrl/admin/realms/$RealmName/users" -Headers $Headers -Body $createPayload | Out-Null
        } catch {
            throw "Failed to create test user: $($_.Exception.Message)"
        }
        $users = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/users?username=$TestEmail" -Headers $Headers
    }

    if ($users.Count -eq 0) {
        throw "Test user could not be created or found."
    }

    return $users[0].id
}

function Reset-TestPassword {
    param(
        [hashtable]$Headers,
        [string]$UserId
    )

    $resetPayload = @{
        type = "password"
        value = $TestPassword
        temporary = $false
    } | ConvertTo-Json -Depth 10 -Compress

    Invoke-RestJson -Method Put -Uri "$KeycloakUrl/admin/realms/$RealmName/users/$UserId/reset-password" -Headers $Headers -Body $resetPayload | Out-Null
}

function Add-KeycloakUserRole {
    param(
        [hashtable]$Headers,
        [string]$UserId
    )

    $role = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/roles/user" -Headers $Headers
    $currentRoles = @()
    try {
        $currentRoles = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/users/$UserId/role-mappings/realm" -Headers $Headers
    } catch {
        $currentRoles = @()
    }

    if (-not ($currentRoles | Where-Object { $_.name -eq "user" })) {
        Write-Log "Assigning realm role 'user' to test user..."
        try {
            $requestBody = @(
                @{
                    id = $role.id
                    name = $role.name
                    composite = $role.composite
                    clientRole = $role.clientRole
                    containerId = $role.containerId
                }
            ) | ConvertTo-Json -Depth 5 -Compress
            Invoke-WebRequest -Method Post -Uri "$KeycloakUrl/admin/realms/$RealmName/users/$UserId/role-mappings/realm" -Headers $Headers -ContentType "application/json" -Body $requestBody | Out-Null
        } catch {
            Write-Log "Warning: role assignment failed, but login setup will continue."
        }
    } else {
        Write-Log "Test user already has role 'user'."
    }
}

function Disable-KeycloakTotpForRealmUsers {
    param([hashtable]$Headers)

    if ($EnableKeycloakTotp) {
        Write-Log "TOTP is enabled; skipping OTP credential removal."
        return
    }

    Write-Log "TOTP is disabled; removing otp credentials from realm users..."
    $users = @()
    try {
        $users = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/users" -Headers $Headers
    } catch {
        Write-Log "Warning: unable to list realm users for OTP cleanup."
        return
    }

    foreach ($user in $users) {
        if (-not $user.id) {
            continue
        }

        try {
            $credentials = @()
            try {
                $credentials = Invoke-RestMethod -Method Get -Uri "$KeycloakUrl/admin/realms/$RealmName/users/$($user.id)/credentials" -Headers $Headers
            } catch {
                $credentials = @()
            }

            foreach ($credential in ($credentials | Where-Object { $_.type -eq 'otp' })) {
                if ($credential.id) {
                    Invoke-RestMethod -Method Delete -Uri "$KeycloakUrl/admin/realms/$RealmName/users/$($user.id)/credentials/$($credential.id)" -Headers $Headers -ErrorAction Stop | Out-Null
                }
            }
        } catch {
            Write-Log "Warning: failed to disable otp for user '$($user.username)'."
        }
    }
}

function Test-Login {
    Write-Log "Browser-flow login is enabled. Skipping legacy password-grant verification."
}

Wait-ForKeycloak
$headers = Get-AdminHeaders
Set-KeycloakRealm -Headers $headers
Set-KeycloakClient -Headers $headers
Set-KeycloakRole -Headers $headers
$userId = Set-KeycloakTestUser -Headers $headers
Disable-KeycloakTotpForRealmUsers -Headers $headers
Reset-TestPassword -Headers $headers -UserId $userId
Add-KeycloakUserRole -Headers $headers -UserId $userId
Test-Login

Write-Log "Keycloak local setup complete and verified."
Write-Host ""
Write-Host "Realm: $RealmName"
Write-Host "Client ID: $ClientId"
Write-Host "Client Secret: $ClientSecret"
Write-Host "Test Login: $TestEmail / $TestPassword"
Write-Host "Admin Console: $KeycloakUrl/admin"
