"""PyJWT RS256 verifier tests: local RSA keypair + in-memory JWKS, no network."""
import base64
import json
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services.jwt_verifier import KeycloakJWTVerifier

ISS = "http://test-kc/realms/test-realm"
KID = "test-key-1"


def _b64u(n: int, size: int) -> str:
    b = n.to_bytes(size, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _make_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = priv.public_key().public_numbers()
    jwk = {
        "kid": KID,
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "n": _b64u(nums.n, 256),
        "e": _b64u(nums.e, 3),
    }
    return priv, jwk


def _token(priv, *, alg="RS256", kid=KID, iss=ISS, aud=None, azp="frontend-app",
           exp_offset=3600, key=None):
    headers = {"alg": alg}
    if kid is not None:
        headers["kid"] = kid
    claims = {
        "iss": iss,
        "sub": "u-1",
        "email": "u@t.t",
        "azp": azp,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "realm_access": {"roles": ["user"]},
    }
    if aud is not None:
        claims["aud"] = aud
    if alg == "none":
        claims_b = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        header_b = base64.urlsafe_b64encode(json.dumps(headers).encode()).rstrip(b"=").decode()
        return f"{header_b}.{claims_b}."
    return pyjwt.encode(claims, key if key is not None else priv,
                        algorithm=alg, headers=headers)


@pytest.fixture()
def verifier(monkeypatch):
    priv, jwk = _make_keypair()
    v = KeycloakJWTVerifier()
    v._jwks = {KID: jwk}
    v._jwks_fetched_at = time.monotonic()
    monkeypatch.setattr(settings, "KEYCLOAK_URL", "http://test-kc")
    monkeypatch.setattr(settings, "KEYCLOAK_REALM", "test-realm")
    monkeypatch.setattr(settings, "KEYCLOAK_AUDIENCE", "")
    monkeypatch.setattr(settings, "KEYCLOAK_ALLOWED_AZP", "frontend-app")
    # no network: _fetch_jwks must never run (cache valid)
    return v, priv


def test_valid_rs256_accepted(verifier):
    v, priv = verifier
    claims = v.verify(_token(priv))
    assert claims and claims["sub"] == "u-1"


def test_expired_rejected(verifier):
    v, priv = verifier
    assert v.verify(_token(priv, exp_offset=-60)) is None


def test_wrong_issuer_rejected(verifier):
    v, priv = verifier
    assert v.verify(_token(priv, iss="http://evil/realms/x")) is None


def test_wrong_kid_rejected(verifier, monkeypatch):
    v, priv = verifier
    other_priv, other_jwk = _make_keypair()
    # unknown kid triggers a forced JWKS refresh; make it fail closed
    monkeypatch.setattr(v, "_fetch_jwks", lambda force=False: None)
    assert v.verify(_token(other_priv, kid="other-kid")) is None


def test_alg_none_rejected(verifier):
    v, _ = verifier
    assert v.verify(_token(None, alg="none")) is None


def test_hs256_confusion_rejected(verifier):
    """HS256 signed with the public JWK JSON as HMAC secret must not verify."""
    v, priv = verifier
    pub_jwk_json = json.dumps(v._jwks[KID])
    forged = _token(priv, alg="HS256", key=pub_jwk_json)
    assert v.verify(forged) is None


def test_tampered_payload_rejected(verifier):
    v, priv = verifier
    tok = _token(priv)
    h, p, s = tok.split(".")
    claims = json.loads(base64.urlsafe_b64decode(p + "=="))
    claims["sub"] = "attacker"
    p2 = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    assert v.verify(f"{h}.{p2}.{s}") is None


def test_missing_kid_rejected(verifier):
    v, priv = verifier
    assert v.verify(_token(priv, kid=None)) is None


def test_wrong_audience_rejected_when_configured(verifier, monkeypatch):
    v, priv = verifier
    monkeypatch.setattr(settings, "KEYCLOAK_AUDIENCE", "expected-aud")
    assert v.verify(_token(priv, aud="wrong-aud")) is None
    assert v.verify(_token(priv, aud="expected-aud")) is not None


def test_disallowed_azp_rejected(verifier):
    v, priv = verifier
    assert v.verify(_token(priv, azp="other-client")) is None


def test_no_exceptions_on_garbage(verifier):
    v, _ = verifier
    assert v.verify("not-a-jwt") is None
    assert v.verify("a.b.c") is None
