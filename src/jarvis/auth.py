"""JWT authentication and device registration for remote access."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_JWT_SECRET = "change-me-in-production"
DEFAULT_JWT_EXPIRY = 86400  # 24 hours
DEFAULT_MAX_DEVICES = 10
DEFAULT_DEVICE_EXPIRY_DAYS = 365

DB_PATH = Path.home() / ".jarvis" / "devices.db"


@dataclass
class Device:
    """Registered device."""

    id: str
    name: str
    api_key: str
    created_at: float
    last_seen: float
    expires_at: float
    is_active: bool = True


@dataclass
class DevicePairingToken:
    """Temporary token for device pairing."""

    token: str
    device_name: str
    created_at: float
    expires_at: float
    is_confirmed: bool = False


@dataclass
class AuthResult:
    """Authentication result."""

    success: bool
    token: str | None = None
    device: Device | None = None
    error: str | None = None


class DeviceRegistry:
    """SQLite-based device registry."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    api_key TEXT UNIQUE NOT NULL,
                    created_at REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pairing_tokens (
                    token TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_confirmed INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def register_device(
        self,
        name: str,
        max_devices: int = DEFAULT_MAX_DEVICES,
        expiry_days: int = DEFAULT_DEVICE_EXPIRY_DAYS,
    ) -> Device:
        """Register a new device."""
        # Check limit
        active_count = self.count_active_devices()
        if active_count >= max_devices:
            raise ValueError(f"Maximum device limit ({max_devices}) reached")

        # Create device
        device_id = secrets.token_urlsafe(16)
        api_key = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + (expiry_days * 86400)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO devices (id, name, api_key, created_at, last_seen, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, name, api_key, now, now, expires_at),
            )
            conn.commit()

        logger.info(f"Registered device: {name} ({device_id})")
        return Device(
            id=device_id,
            name=name,
            api_key=api_key,
            created_at=now,
            last_seen=now,
            expires_at=expires_at,
        )

    def get_device_by_api_key(self, api_key: str) -> Device | None:
        """Get device by API key."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT * FROM devices WHERE api_key = ? AND is_active = 1
                """,
                (api_key,),
            )
            row = cur.fetchone()

        if not row:
            return None

        return Device(
            id=row["id"],
            name=row["name"],
            api_key=row["api_key"],
            created_at=row["created_at"],
            last_seen=row["last_seen"],
            expires_at=row["expires_at"],
            is_active=bool(row["is_active"]),
        )

    def update_last_seen(self, device_id: str) -> None:
        """Update device last seen timestamp."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE devices SET last_seen = ? WHERE id = ?",
                (time.time(), device_id),
            )
            conn.commit()

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "UPDATE devices SET is_active = 0 WHERE id = ?",
                (device_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_devices(self) -> list[Device]:
        """List all devices."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM devices ORDER BY created_at DESC")
            rows = cur.fetchall()

        return [
            Device(
                id=row["id"],
                name=row["name"],
                api_key=row["api_key"],
                created_at=row["created_at"],
                last_seen=row["last_seen"],
                expires_at=row["expires_at"],
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def count_active_devices(self) -> int:
        """Count active devices."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM devices WHERE is_active = 1"
            )
            return cur.fetchone()[0]

    def cleanup_expired(self) -> int:
        """Remove expired devices."""
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM devices WHERE expires_at < ? OR is_active = 0",
                (now,),
            )
            conn.commit()
            return cur.rowcount


class PairingManager:
    """Manage device pairing tokens."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize pairing tokens table."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pairing_tokens (
                    token TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_confirmed INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def create_token(self, device_name: str, ttl: int = 300) -> DevicePairingToken:
        """Create a pairing token (5 min TTL)."""
        token = secrets.token_urlsafe(16)
        now = time.time()
        expires_at = now + ttl

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO pairing_tokens (token, device_name, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, device_name, now, expires_at),
            )
            conn.commit()

        return DevicePairingToken(
            token=token,
            device_name=device_name,
            created_at=now,
            expires_at=expires_at,
        )

    def get_token(self, token: str) -> DevicePairingToken | None:
        """Get pairing token."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM pairing_tokens WHERE token = ?",
                (token,),
            )
            row = cur.fetchone()

        if not row:
            return None

        return DevicePairingToken(
            token=row["token"],
            device_name=row["device_name"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            is_confirmed=bool(row["is_confirmed"]),
        )

    def confirm_token(self, token: str) -> bool:
        """Mark token as confirmed."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "UPDATE pairing_tokens SET is_confirmed = 1 WHERE token = ?",
                (token,),
            )
            conn.commit()
            return cur.rowcount > 0

    def cleanup_expired(self) -> int:
        """Remove expired tokens."""
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM pairing_tokens WHERE expires_at < ? OR is_confirmed = 1",
                (now,),
            )
            conn.commit()
            return cur.rowcount


class JWTAuth:
    """JWT token generation and validation."""

    def __init__(
        self,
        secret: str | None = None,
        expiry_seconds: int = DEFAULT_JWT_EXPIRY,
    ):
        if not HAS_JWT:
            raise ImportError("pyjwt is required. Install with: pip install pyjwt")

        self._secret = secret or os.environ.get(
            "JARVIS_JWT_SECRET", DEFAULT_JWT_SECRET
        )
        self._expiry = expiry_seconds

    def generate_token(self, device: Device) -> str:
        """Generate JWT token for a device."""
        payload = {
            "device_id": device.id,
            "device_name": device.name,
            "iat": int(time.time()),
            "exp": int(time.time()) + self._expiry,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def validate_token(self, token: str) -> AuthResult:
        """Validate JWT token and return device info."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            return AuthResult(
                success=True,
                token=token,
                error=None,
            )
        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return AuthResult(success=False, error=f"Invalid token: {e}")

    def decode_payload(self, token: str) -> dict[str, Any] | None:
        """Decode token payload without validation (for debugging)."""
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None


class Authenticator:
    """Main authentication interface."""

    def __init__(
        self,
        secret: str | None = None,
        expiry_seconds: int = DEFAULT_JWT_EXPIRY,
        max_devices: int = DEFAULT_MAX_DEVICES,
        db_path: Path = DB_PATH,
    ):
        self._jwt = JWTAuth(secret, expiry_seconds)
        self._devices = DeviceRegistry(db_path)
        self._pairing = PairingManager(db_path)
        self._max_devices = max_devices

    @property
    def devices(self) -> DeviceRegistry:
        return self._devices

    @property
    def pairing(self) -> PairingManager:
        return self._pairing

    def initiate_pairing(self, device_name: str) -> dict[str, Any]:
        """Start device pairing process."""
        # Cleanup expired
        self._pairing.cleanup_expired()

        # Create pairing token
        pairing_token = self._pairing.create_token(device_name)

        # QR code data
        qr_data = {
            "type": "jarvis_pairing",
            "token": pairing_token.token,
            "device_name": device_name,
            "server": os.environ.get("JARVIS_REMOTE_HOST", "localhost:9848"),
        }

        return {
            "token": pairing_token.token,
            "qr_data": json.dumps(qr_data),
            "expires_at": pairing_token.expires_at,
        }

    def confirm_pairing(self, token: str) -> dict[str, Any] | None:
        """Confirm pairing and return API key + JWT."""
        pairing = self._pairing.get_token(token)
        if not pairing:
            return None

        if pairing.is_confirmed:
            return None

        if time.time() > pairing.expires_at:
            return None

        # Register device
        try:
            device = self._devices.register_device(
                pairing.device_name,
                max_devices=self._max_devices,
            )
        except ValueError as e:
            return {"error": str(e)}

        # Mark token as confirmed
        self._pairing.confirm_token(token)

        # Generate JWT
        jwt_token = self._jwt.generate_token(device)

        return {
            "device_id": device.id,
            "api_key": device.api_key,
            "jwt": jwt_token,
            "expires_at": device.expires_at,
        }

    def authenticate(self, token: str) -> AuthResult:
        """Authenticate a JWT token."""
        result = self._jwt.validate_token(token)
        if not result.success:
            return result

        # Extract device info from token
        payload = self._jwt.decode_payload(token)
        if not payload:
            return AuthResult(success=False, error="Invalid token payload")

        device_id = payload.get("device_id")
        if not device_id:
            return AuthResult(success=False, error="Missing device_id")

        # Verify device exists and is active
        device = self._devices.get_device_by_api_key(token)  # JWT IS api_key for now
        if not device:
            return AuthResult(success=False, error="Device not found")

        # Update last seen
        self._devices.update_last_seen(device.id)

        result.device = device
        return result

    def authenticate_api_key(self, api_key: str) -> Device | None:
        """Authenticate via API key (for initial pairing)."""
        return self._devices.get_device_by_api_key(api_key)

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device."""
        return self._devices.revoke_device(device_id)

    def list_devices(self) -> list[Device]:
        """List all devices."""
        return self._devices.list_devices()

    def cleanup(self) -> None:
        """Cleanup expired devices and tokens."""
        self._devices.cleanup_expired()
        self._pairing.cleanup_expired()


def generate_jwt_secret() -> str:
    """Generate a secure random JWT secret."""
    return secrets.token_urlsafe(32)


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC signature."""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
