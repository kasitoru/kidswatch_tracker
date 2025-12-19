"""KidsWatchAPI for Kids Watch Tracker integration"""

import json
import os
import hashlib
import time
import base64
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, List
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import ssl
import uuid

class KidsWatchAPI:
    
    API_URL = "https://api.kidswatch-sg.com/v2/"
    APP_VER = "3.2.1"
    
    def __init__(self):
        self.user: Optional[Dict[str, Any]] = None
        self.error: str = None
    
    def last_error(self) -> str:
        """Getting the latest error message"""
        return self.error
    
    def login(self, country_code: str, phone_number: str, password: str, user_lang: str = "en_US", time_zone: str = "UTC", timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Authentication (returns authorization data)"""
        result = None
        response = self._api_request("login/postIndex", {
            "country_code": country_code,
            "password": hashlib.md5(password.encode()).hexdigest(),
            "phone_number": phone_number,
            "user_lang": user_lang,
            "time_zone": time_zone,
        }, timeout)
        if response:
            # Remove unnecessary fields
            response.pop("retcode", None)
            response.pop("errcode", None)
            result = response
        return result
    
    def set_auth_data(self, user: Dict[str, Any]) -> bool:
        """Set authorization data"""
        if isinstance(user, dict) and all(key in user for key in ["token", "secret", "qid"]):
            self.user = user
            return True
        return False
    
    def get_kids(self, timeout: float = 30.0) -> Optional[List[Dict[str, Any]]]:
        """Get list of children"""
        response = self._api_request("parents/kids", None, timeout)
        if response is not None:
            return response.get("kids_list", [])
        return None
    
    def request_current_position(self, device_id: str, timeout: float = 30.0) -> bool:
        """Request current device position"""
        return self._api_request("kids/currentpos", {
            "device_id": device_id,
        }, timeout)
    
    def get_last_position(self, device_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Get last device position"""
        response = self._api_request("kids/lastpos", {
            "device_id": device_id,
        }, timeout)
        if response is not None:
            position = response.get("device_pos")
            if position:
                return position[0]
            else:
                self.error = "Location data is unavailable"
        return None
    
    def _get_key(self, device_id: str, seed: str, timestamp: int) -> bytes:
        """"Encryption key calculation"""
        md5_ts = hashlib.md5(str(timestamp).encode()).hexdigest()
        md5_id1 = hashlib.md5(device_id[9:25].encode()).hexdigest()
        if self.user:
            md5_qid = hashlib.md5(self.user.get("qid").encode()).hexdigest()
            array = [seed, self.user.get("token"), self.user.get("secret"), md5_qid, md5_ts]
        else:
            array = [seed, md5_id1, md5_ts]
        concat = "".join(sorted(array))
        key_md5 = hashlib.md5(concat.encode()).hexdigest()
        return key_md5.encode()
    
    def _get_iv(self, device_id: str, seed: str, timestamp: int) -> bytes:
        """Initialization vector calculation"""
        md5_seed = hashlib.md5(seed.encode()).hexdigest()
        md5_id2 = hashlib.md5(device_id[16:25].encode()).hexdigest()
        md5_ts = hashlib.md5(str(timestamp).encode()).hexdigest()
        if self.user:
            md5_secret = hashlib.md5(self.user.get("secret").encode()).hexdigest()
            md5_qid = hashlib.md5(self.user.get("qid").encode()).hexdigest()
            array = [md5_seed, md5_secret, md5_qid, md5_ts]
        else:
            array = [md5_seed, md5_id2, md5_ts]
        concat = "".join(sorted(array))
        iv_md5 = hashlib.md5(concat.encode()).hexdigest()
        return iv_md5[9:25].encode()
    
    def _encrypt_data(self, data: str, device_id: str, seed: str, timestamp: int) -> Optional[str]:
        """Data encryption"""
        try:
            key = self._get_key(device_id, seed, timestamp)
            iv = self._get_iv(device_id, seed, timestamp)
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data.encode()) + padder.finalize()
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            return base64.b64encode(encrypted).decode()
        except Exception as error:
            self.error = str(error)
            return None
    
    def _decrypt_data(self, data: str, device_id: str, seed: str, timestamp: int) -> Optional[str]:
        """Data decryption"""
        try:
            encrypted_bytes = base64.b64decode(data)
            key = self._get_key(device_id, seed, timestamp)
            iv = self._get_iv(device_id, seed, timestamp)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_bytes) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            unpadded = unpadder.update(decrypted) + unpadder.finalize()
            return unpadded.decode()
        except Exception as error:
            self.error = str(error)
            return None
    
    def _get_device_id(self) -> str:
        """Unique device identifier"""
        mac_address = str(uuid.getnode())
        return hashlib.md5(mac_address.encode()).hexdigest()
    
    def _generate_seed(self) -> str:
        """Generate seed string"""
        random_bytes = os.urandom(16)
        raw = random_bytes.hex().upper()
        return hashlib.md5(raw.encode()).hexdigest()
    
    def _get_timestamp(self) -> int:
        """Get timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def _api_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Execute API request"""
        if data is None:
            data = {}
        # Add required data to request
        data.update({
            "m2": self._get_device_id(),
            "seed": self._generate_seed(),
            "ts": self._get_timestamp(),
        })
        # Form query parameters for URL
        query_params = {
            "id": hashlib.md5(data.get("m2").encode()).hexdigest(),
            "seed": data.get("seed"),
            "token": self.user.get("token", "") if self.user else "",
            "ts": data.get("ts"),
        }
        url = f"{self.API_URL}{endpoint}?{urllib.parse.urlencode(query_params)}"
        # Encrypt data
        encrypted_data = self._encrypt_data(urllib.parse.urlencode(data), query_params.get("id"), data.get("seed"), data.get("ts"))
        if not encrypted_data:
            return None
        # Prepare request
        post_data = urllib.parse.urlencode({"p": encrypted_data}).encode()
        headers = {
            "User-Agent": f"KidsV2-Android-{self.APP_VER}",
            "Accept-Language": self.user.get("user_lang", "en_US") if self.user else "en_US",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            req = urllib.request.Request(url, data=post_data, headers=headers, method="POST")
            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
                response_data = response.read().decode("utf-8")
                # Check if decryption is required
                if response.headers.get("Encrypt", "0") == "1":
                    decrypted = self._decrypt_data(response_data, query_params.get("id"), data.get("seed"), data.get("ts"))
                    if decrypted is None:
                        return None
                    response_data = decrypted
                # Check if response is JSON
                if "application/json" in response.headers.get("Content-Type", "").lower():
                    try:
                        json_response = json.loads(response_data)
                        # Check for errors
                        if json_response.get("retcode", 0) != 0:
                            self.error = json_response.get("errmsg", "Unknown error")
                            return None
                        return json_response
                    except json.JSONDecodeError as error:
                        self.error = f"JSON decode error: {str(error)}"
                        return None
                else:
                    # If not JSON, return as is
                    return {"raw_response": response_data}
        except urllib.error.HTTPError as error:
            self.error = f"HTTP Error: {error.reason}"
            return None
        except urllib.error.URLError as error:
            self.error = f"URL Error: {error.reason}"
            return None
        except Exception as error:
            self.error = str(error)
            return None
