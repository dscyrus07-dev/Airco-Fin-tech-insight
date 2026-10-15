"""Create avadmin test user with realm role 'admin' in airco-insights realm.
Prints only status booleans; never prints secrets."""
import json, os, urllib.request, urllib.parse

KC = "http://localhost:8080"
REALM = "airco-insights"
CLIENT = "frontend-app"
EMAIL = "avadmin@airco.com"
PW = "AvTest!234"  # synthetic local fixture, recorded in README


def call(method, path, tok=None, body=None):
    r = urllib.request.Request(KC + path, data=json.dumps(body).encode() if body is not None else None,
                               method=method,
                               headers={"Authorization": f"Bearer {tok}"} if tok else {})
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def admin_token():
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                   "username": os.environ["KEYCLOAK_ADMIN"],
                                   "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"]}).encode()
    r = urllib.request.Request(f"{KC}/realms/master/protocol/openid-connect/token", data=data)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def main():
    at = admin_token()
    # ensure realm role 'admin'
    s, _ = call("GET", f"/admin/realms/{REALM}/roles/admin", at)
    if s == 404:
        s2, _ = call("POST", f"/admin/realms/{REALM}/roles", at, {"name": "admin"})
        print("role admin created:", s2 in (201, 409))
        s, _ = call("GET", f"/admin/realms/{REALM}/roles/admin", at)
    role = json.loads(_)
    # user
    s, users = call("GET", f"/admin/realms/{REALM}/users?username={EMAIL}", at)
    users = json.loads(users)
    if users:
        uid = users[0]["id"]
        call("PUT", f"/admin/realms/{REALM}/users/{uid}", at,
             {"firstName": "AV", "lastName": "Admin", "emailVerified": True, "enabled": True})
        call("PUT", f"/admin/realms/{REALM}/users/{uid}/reset-password", at,
             {"type": "password", "value": PW, "temporary": False})
    else:
        s, _ = call("POST", f"/admin/realms/{REALM}/users", at,
                    {"username": EMAIL, "email": EMAIL, "enabled": True,
                     "firstName": "AV", "lastName": "Admin", "emailVerified": True,
                     "credentials": [{"type": "password", "value": PW, "temporary": False}]})
        s, users = call("GET", f"/admin/realms/{REALM}/users?username={EMAIL}", at)
        uid = json.loads(users)[0]["id"]
    s, _ = call("POST", f"/admin/realms/{REALM}/users/{uid}/role-mappings/realm", at, [role])
    print("role mapped:", s in (204, 409))
    # verify ROPC + role in token
    import base64
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": CLIENT,
                                   "username": EMAIL, "password": PW}).encode()
    r = urllib.request.Request(f"{KC}/realms/{REALM}/protocol/openid-connect/token", data=data)
    with urllib.request.urlopen(r, timeout=30) as resp:
        tok = json.loads(resp.read())["access_token"]
    claims = json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "=="))
    print("admin in realm_access.roles:", "admin" in (claims.get("realm_access") or {}).get("roles", []))


if __name__ == "__main__":
    main()
