"""Asynchronous API client for the Kids Watch cloud."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.parse
import uuid
from typing import Any

import aiohttp
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

API_URL = "https://api.kidswatch-sg.com/v2/"
APP_VER = "3.2.1"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# retcode values meaning "invalid credentials / expired token".
# The protocol is not publicly documented: fill this set from real responses
# (every KidsWatchApiError contains the retcode and is logged by the coordinator).
AUTH_RETCODES: frozenset[int] = frozenset()
# Fallback heuristic until AUTH_RETCODES is filled in.
AUTH_ERROR_MARKERS = ("token", "login", "auth")


class KidsWatchError(Exception):
    """Base Kids Watch API error."""


class KidsWatchConnectionError(KidsWatchError):
    """Network or transport error."""


class KidsWatchAuthError(KidsWatchError):
    """Credentials rejected or session expired."""


class KidsWatchApiError(KidsWatchError):
    """API returned a non-zero retcode."""

    def __init__(self, retcode: int | None, message: str) -> None:
        """Initialize the error."""
        super().__init__(f"API error {retcode}: {message}")
        self.retcode = retcode


class KidsWatchAPI:
    """Kids Watch cloud API client."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with a shared aiohttp session."""
        self._session = session
        self._user: dict[str, Any] | None = None
        self._device_id = hashlib.md5(str(uuid.getnode()).encode()).hexdigest()

    def set_auth_data(self, user: dict[str, Any] | None) -> bool:
        """Set authorization data."""
        if isinstance(user, dict) and all(key in user for key in ("token", "secret", "qid")):
            self._user = user
            return True
        return False

    async def login(
        self,
        country_code: str,
        phone_number: str,
        password: str,
        user_lang: str = "en_US",
        time_zone: str = "UTC",
    ) -> dict[str, Any]:
        """Authenticate and return authorization data."""
        response = await self._request("login/postIndex", {
            "country_code": country_code,
            "password": hashlib.md5(password.encode()).hexdigest(),
            "phone_number": phone_number,
            "user_lang": user_lang,
            "time_zone": time_zone,
        })
        response.pop("retcode", None)
        response.pop("errcode", None)
        return response

    async def get_kids(self) -> list[dict[str, Any]]:
        """Get the list of children."""
        response = await self._request("parents/kids")
        return response.get("kids_list", [])

    async def get_last_position(self, device_id: str) -> dict[str, Any] | None:
        """Get the last known position of the device."""
        response = await self._request("kids/lastpos", {"device_id": device_id})
        positions = response.get("device_pos")
        return positions[0] if positions else None

    async def request_current_position(self, device_id: str) -> None:
        """Ask the device to report its current position."""
        await self._request("kids/currentpos", {"device_id": device_id})

    def _get_key(self, device_id: str, seed: str, timestamp: int) -> bytes:
        """Encryption key calculation."""
        md5_ts = hashlib.md5(str(timestamp).encode()).hexdigest()
        if self._user:
            md5_qid = hashlib.md5(self._user["qid"].encode()).hexdigest()
            array = [seed, self._user["token"], self._user["secret"], md5_qid, md5_ts]
        else:
            md5_id1 = hashlib.md5(device_id[9:25].encode()).hexdigest()
            array = [seed, md5_id1, md5_ts]
        return hashlib.md5("".join(sorted(array)).encode()).hexdigest().encode()

    def _get_iv(self, device_id: str, seed: str, timestamp: int) -> bytes:
        """Initialization vector calculation."""
        md5_seed = hashlib.md5(seed.encode()).hexdigest()
        md5_ts = hashlib.md5(str(timestamp).encode()).hexdigest()
        if self._user:
            md5_secret = hashlib.md5(self._user["secret"].encode()).hexdigest()
            md5_qid = hashlib.md5(self._user["qid"].encode()).hexdigest()
            array = [md5_seed, md5_secret, md5_qid, md5_ts]
        else:
            md5_id2 = hashlib.md5(device_id[16:25].encode()).hexdigest()
            array = [md5_seed, md5_id2, md5_ts]
        return hashlib.md5("".join(sorted(array)).encode()).hexdigest()[9:25].encode()

    def _encrypt_data(self, data: str, device_id: str, seed: str, timestamp: int) -> str:
        """Data encryption."""
        try:
            key = self._get_key(device_id, seed, timestamp)
            iv = self._get_iv(device_id, seed, timestamp)
            padder = padding.PKCS7(128).padder()
            padded = padder.update(data.encode()) + padder.finalize()
            encryptor = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).encryptor()
            return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()
        except Exception as err:
            raise KidsWatchError(f"Encryption error: {err}") from err

    def _decrypt_data(self, data: str, device_id: str, seed: str, timestamp: int) -> str:
        """Data decryption."""
        try:
            key = self._get_key(device_id, seed, timestamp)
            iv = self._get_iv(device_id, seed, timestamp)
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            decrypted = decryptor.update(base64.b64decode(data)) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            return (unpadder.update(decrypted) + unpadder.finalize()).decode()
        except Exception as err:
            raise KidsWatchError(f"Decryption error: {err}") from err

    @staticmethod
    def _generate_seed() -> str:
        """Generate a seed string."""
        return hashlib.md5(os.urandom(16).hex().upper().encode()).hexdigest()

    @staticmethod
    def _get_timestamp() -> int:
        """Get a timestamp in milliseconds."""
        return int(time.time() * 1000)

    async def _request(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an API request."""
        data = dict(data or {})
        data.update({
            "m2": self._device_id,
            "seed": self._generate_seed(),
            "ts": self._get_timestamp(),
        })
        query = {
            "id": hashlib.md5(data["m2"].encode()).hexdigest(),
            "seed": data["seed"],
            "token": self._user.get("token", "") if self._user else "",
            "ts": data["ts"],
        }
        encrypted = self._encrypt_data(
            urllib.parse.urlencode(data), query["id"], data["seed"], data["ts"]
        )
        headers = {
            "User-Agent": f"KidsV2-Android-{APP_VER}",
            "Accept-Language": self._user.get("user_lang", "en_US") if self._user else "en_US",
        }
        try:
            async with self._session.post(
                f"{API_URL}{endpoint}",
                params=query,
                data={"p": encrypted},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                text = await response.text()
                if response.headers.get("Encrypt", "0") == "1":
                    text = self._decrypt_data(text, query["id"], data["seed"], data["ts"])
                content_type = response.headers.get("Content-Type", "").lower()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KidsWatchConnectionError(f"{type(err).__name__}: {err}") from err

        if "application/json" not in content_type:
            return {"raw_response": text}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as err:
            raise KidsWatchApiError(None, f"Invalid JSON response: {err}") from err

        retcode = payload.get("retcode", 0)
        if retcode != 0:
            message = payload.get("errmsg", "Unknown error")
            if retcode in AUTH_RETCODES or any(
                marker in message.lower() for marker in AUTH_ERROR_MARKERS
            ):
                raise KidsWatchAuthError(message)
            raise KidsWatchApiError(retcode, message)
        return payload
