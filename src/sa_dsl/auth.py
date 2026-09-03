from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


COGNITO_REGION = "us-east-1"
COGNITO_USER_POOL_ID = "us-east-1_BAngPH8Of"
COGNITO_CLIENT_ID = "oko6nglr3pu3v2j9rbpvgkmon"
COGNITO_ENDPOINT = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"

_N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64"
    "ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
    "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6"
    "BF12FFA06D98A0864D87602733EC86A64521F2B18177B200"
    "CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3"
    "143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)
_N = int(_N_HEX, 16)
_G = 2


class _Response(Protocol):
    def read(self) -> bytes: ...
    def __enter__(self) -> _Response: ...
    def __exit__(self, *args: object) -> None: ...


class AuthenticationError(RuntimeError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.details = details


def load_env(path: str | Path = ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _pad_hex(value: int) -> str:
    result = format(value, "x")
    if len(result) % 2:
        result = f"0{result}"
    elif result[0] in "89abcdefABCDEF":
        result = f"00{result}"
    return result


def _hex_hash(value: str) -> int:
    return int(hashlib.sha256(bytes.fromhex(value)).hexdigest(), 16)


def _hkdf(ikm: bytes, salt: bytes) -> bytes:
    pseudo_random_key = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(
        pseudo_random_key, b"Caldera Derived Key\x01", hashlib.sha256
    ).digest()[:16]


def _timestamp(now: dt.datetime) -> str:
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    return (
        f"{weekdays[now.weekday()]} {months[now.month - 1]} {now.day} "
        f"{now:%H:%M:%S} UTC {now.year}"
    )


class CognitoAuthenticator:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        user_pool_id: str = COGNITO_USER_POOL_ID,
        client_id: str = COGNITO_CLIENT_ID,
        endpoint: str = COGNITO_ENDPOINT,
        timeout: float = 30,
        opener: Callable[..., _Response] | None = None,
    ) -> None:
        if not username or not password:
            raise ValueError("username and password must be non-empty")
        self.username = username
        self.password = password
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.endpoint = endpoint
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def _request(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": f"AWSCognitoIdentityProviderService.{operation}",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            content = error.read().decode("utf-8", errors="replace")
            try:
                details = json.loads(content)
            except json.JSONDecodeError:
                details = content
            message = details.get("message") if isinstance(details, dict) else content
            raise AuthenticationError(message or "Cognito authentication failed", details=details) from error
        except urllib.error.URLError as error:
            raise AuthenticationError(f"Cannot reach Cognito: {error.reason}") from error

    def authenticate(self) -> str:
        small_a = int.from_bytes(secrets.token_bytes(128), "big") % _N
        large_a = pow(_G, small_a, _N)
        if large_a % _N == 0:
            raise AuthenticationError("Invalid SRP public value")

        initiated = self._request(
            "InitiateAuth",
            {
                "AuthFlow": "USER_SRP_AUTH",
                "ClientId": self.client_id,
                "AuthParameters": {
                    "USERNAME": self.username,
                    "SRP_A": format(large_a, "x"),
                },
            },
        )
        if initiated.get("ChallengeName") != "PASSWORD_VERIFIER":
            raise AuthenticationError(
                f"Unsupported Cognito challenge: {initiated.get('ChallengeName', 'none')}",
                details=initiated,
            )
        parameters = initiated["ChallengeParameters"]
        user_id = parameters["USER_ID_FOR_SRP"]
        large_b = int(parameters["SRP_B"], 16)
        salt = int(parameters["SALT"], 16)
        if large_b % _N == 0:
            raise AuthenticationError("Invalid SRP server value")

        k = _hex_hash(f"00{_N_HEX}0{_G:x}")
        u = _hex_hash(f"{_pad_hex(large_a)}{_pad_hex(large_b)}")
        if u == 0:
            raise AuthenticationError("Invalid SRP scrambling parameter")
        pool_name = self.user_pool_id.split("_", 1)[1]
        user_password_hash = _hash(
            f"{pool_name}{user_id}:{self.password}".encode("utf-8")
        )
        x = _hex_hash(f"{_pad_hex(salt)}{user_password_hash.hex()}")
        value = (large_b - k * pow(_G, x, _N)) % _N
        shared_secret = pow(value, small_a + u * x, _N)
        key = _hkdf(
            bytes.fromhex(_pad_hex(shared_secret)),
            bytes.fromhex(_pad_hex(u)),
        )
        secret_block = base64.b64decode(parameters["SECRET_BLOCK"])
        timestamp = _timestamp(dt.datetime.now(dt.UTC))
        signature = base64.b64encode(
            hmac.new(
                key,
                pool_name.encode("utf-8")
                + user_id.encode("utf-8")
                + secret_block
                + timestamp.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        completed = self._request(
            "RespondToAuthChallenge",
            {
                "ChallengeName": "PASSWORD_VERIFIER",
                "ClientId": self.client_id,
                "ChallengeResponses": {
                    "USERNAME": user_id,
                    "PASSWORD_CLAIM_SECRET_BLOCK": parameters["SECRET_BLOCK"],
                    "TIMESTAMP": timestamp,
                    "PASSWORD_CLAIM_SIGNATURE": signature,
                },
                "Session": initiated.get("Session"),
            },
        )
        token = (completed.get("AuthenticationResult") or {}).get("IdToken")
        if not token:
            challenge = completed.get("ChallengeName", "unknown")
            raise AuthenticationError(
                f"Cognito requires unsupported follow-up challenge: {challenge}",
                details=completed,
            )
        return token
