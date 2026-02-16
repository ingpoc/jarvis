"""Remote WebSocket server with WSS, JWT auth, and REST API.

Separate from local ws_server.py (port 9847).
Listens on 0.0.0.0:9848 for remote connections via Tailscale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import websockets
    from websockets.server import serve

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

if TYPE_CHECKING:
    from jarvis.events import EventCollector
    from jarvis.orchestrator import JarvisOrchestrator
    from jarvis.auth import Authenticator

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9848
DEFAULT_BIND = "0.0.0.0"


def _require_websockets():
    if not HAS_WEBSOCKETS:
        raise ImportError(
            "websockets is required for remote server. "
            "Install with: pip install websockets"
        )


class RateLimiter:
    """Simple rate limiter per device."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, device_id: str) -> bool:
        """Check if request is allowed."""
        now = asyncio.get_event_loop().time()
        requests = self._requests.get(device_id, [])

        # Remove old requests
        requests = [t for t in requests if now - t < self._window]

        if len(requests) >= self._max:
            return False

        requests.append(now)
        self._requests[device_id] = requests
        return True

    def reset(self, device_id: str) -> None:
        """Reset rate limit for device."""
        self._requests.pop(device_id, None)


class JarvisRemoteServer:
    """Remote-capable WebSocket server with JWT authentication."""

    def __init__(
        self,
        event_collector: EventCollector,
        orchestrator: JarvisOrchestrator | None = None,
        authenticator: Authenticator | None = None,
        port: int = DEFAULT_PORT,
        bind: str = DEFAULT_BIND,
        ssl_cert_path: str | None = None,
        ssl_key_path: str | None = None,
    ):
        _require_websockets()
        self._events = event_collector
        self._orchestrator = orchestrator
        self._auth = authenticator
        self._port = port
        self._bind = bind
        self._ssl_cert_path = ssl_cert_path
        self._ssl_key_path = ssl_key_path

        self._clients: dict = {}  # ws -> device_id
        self._devices: dict = {}  # device_id -> ws
        self._server = None
        self._rate_limiter = RateLimiter()

        # Register as EventCollector listener
        self._events.add_listener(self._broadcast_event)

    async def start(self) -> None:
        """Start WSS server on 0.0.0.0."""
        # Create SSL context for WSS
        ssl_context = None
        if self._ssl_cert_path and self._ssl_key_path:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self._ssl_cert_path, self._ssl_key_path)
            logger.info(f"WSS mode enabled with cert: {self._ssl_cert_path}")
        else:
            # Generate self-signed cert for development
            ssl_context = self._generate_self_signed_cert()
            if ssl_context:
                logger.info("WSS mode enabled with self-signed certificate")

        self._server = await serve(
            self._handler,
            self._bind,
            self._port,
            ssl=ssl_context,
        )
        logger.info(f"Remote WSS server listening on {self._bind}:{self._port}")

    def _generate_self_signed_cert(self) -> ssl.SSLContext | None:
        """Generate self-signed certificate for development."""
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import ipaddress

            # Generate private key
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )

            # Generate certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Jarvis"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
                ]),
                critical=False,
            ).sign(key, hashes.SHA256(), default_backend())

            # Write to temp files
            cert_dir = Path.home() / ".jarvis" / "certs"
            cert_dir.mkdir(parents=True, exist_ok=True)

            cert_path = cert_dir / "server.crt"
            key_path = cert_dir / "server.key"

            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(key_path, "wb") as f:
                f.write(
                    key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.TraditionalOpenSSL,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            self._ssl_cert_path = str(cert_path)
            self._ssl_key_path = str(key_path)

            # Create SSL context
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert_path), str(key_path))
            return context

        except ImportError:
            logger.warning("cryptography not installed, using WS (not WSS)")
            return None
        except Exception as e:
            logger.error(f"Failed to generate self-signed cert: {e}")
            return None

    async def stop(self) -> None:
        """Close the server and all connections."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Remote WSS server stopped")

        # Remove listener
        self._events.remove_listener(self._broadcast_event)

    async def _handler(self, websocket) -> None:
        """Handle a single client connection with JWT auth."""
        remote = websocket.remote_address
        logger.info(f"Remote client connecting: {remote}")

        # Wait for auth message
        try:
            auth_raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_msg = json.loads(auth_raw)

            if auth_msg.get("type") == "auth":
                token = auth_msg.get("token", "")
                result = self._authenticate_connection(websocket, token, remote)
                if not result:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "data": {"message": "Authentication failed"},
                    }))
                    await websocket.close()
                    return
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "data": {"message": "Auth required"},
                }))
                await websocket.close()
                return

        except asyncio.TimeoutError:
            logger.warning(f"Auth timeout from {remote}")
            await websocket.close()
            return
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Auth error from {remote}: {e}")
            await websocket.close()
            return

        # Authenticated - handle messages
        logger.info(f"Client authenticated: {remote}")

        try:
            async for raw in websocket:
                try:
                    cmd_data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "data": {"message": "Invalid JSON"},
                    }))
                    continue

                await self._handle_command(websocket, cmd_data)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._remove_client(websocket)

    def _authenticate_connection(self, ws, token: str, remote) -> bool:
        """Authenticate a WebSocket connection."""
        if not self._auth:
            logger.warning("No authenticator configured")
            return False

        result = self._auth.authenticate(token)
        if not result.success:
            logger.warning(f"Auth failed for {remote}: {result.error}")
            return False

        device_id = result.device.id
        self._clients[ws] = device_id
        self._devices[device_id] = ws

        logger.info(f"Authenticated: {result.device.name} ({device_id})")

        # Send auth success
        asyncio.create_task(ws.send(json.dumps({
            "type": "auth_success",
            "data": {
                "device_id": device_id,
                "device_name": result.device.name,
            },
        })))

        return True

    def _remove_client(self, ws) -> None:
        """Remove client from tracking."""
        device_id = self._clients.pop(ws, None)
        if device_id:
            self._devices.pop(device_id, None)
        remote = getattr(ws, "remote_address", "unknown")
        logger.info(f"Client disconnected: {remote}")

    async def _handle_command(self, ws, cmd_data: dict) -> None:
        """Dispatch a command from an authenticated client."""
        device_id = self._clients.get(ws)
        if not device_id:
            await ws.send(json.dumps({
                "type": "error",
                "data": {"message": "Not authenticated"},
            }))
            return

        # Rate limit check
        if not self._rate_limiter.is_allowed(device_id):
            await ws.send(json.dumps({
                "type": "error",
                "data": {"message": "Rate limit exceeded"},
            }))
            return

        action = cmd_data.get("action", "")
        data = cmd_data.get("data", {})
        result: Any = None

        try:
            if action == "get_status":
                if self._orchestrator:
                    result = await self._orchestrator.get_status()
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_timeline":
                if self._orchestrator:
                    limit = data.get("limit", 50)
                    result = self._orchestrator.memory.get_timeline(limit=limit)
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "approve":
                task_id = data.get("task_id", "")
                self._events.emit(
                    "approval_granted",
                    f"Approved via Remote: {task_id}",
                    task_id=task_id,
                    metadata={"device_id": device_id},
                )
                result = {"approved": task_id}

            elif action == "deny":
                task_id = data.get("task_id", "")
                self._events.emit(
                    "approval_denied",
                    f"Denied via Remote: {task_id}",
                    task_id=task_id,
                    metadata={"device_id": device_id},
                )
                result = {"denied": task_id}

            elif action == "run_task":
                description = data.get("description", "")
                if not description:
                    result = {"error": "Missing 'description'"}
                elif self._orchestrator:
                    asyncio.create_task(
                        self._orchestrator.run_task(description)
                    )
                    result = {"queued": description[:100]}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "send_voice":
                text = data.get("text", "")
                if text and self._orchestrator:
                    self._events.emit(
                        "voice_input",
                        f"Voice from {device_id}",
                        metadata={"text": text, "device_id": device_id},
                    )
                    result = {"processed": text[:100]}
                else:
                    result = {"error": "Missing text"}

            else:
                result = {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Command error ({action}) from {device_id}: {e}")
            result = {"error": str(e)}

        response = {"type": "response", "action": action, "data": result}
        await ws.send(json.dumps(response, default=str))

    def _broadcast_event(self, event_data: dict) -> None:
        """EventCollector listener callback: push events to all authenticated clients."""
        if not self._clients:
            return

        message = json.dumps(
            {"type": "event", "data": event_data},
            default=str,
        )

        stale: set = set()
        for ws, device_id in self._clients.items():
            try:
                asyncio.ensure_future(ws.send(message))
            except Exception:
                stale.add(ws)

        for ws in stale:
            self._remove_client(ws)

    async def send_to_device(self, device_id: str, message: dict) -> bool:
        """Send message to specific device."""
        ws = self._devices.get(device_id)
        if not ws:
            return False

        try:
            await ws.send(json.dumps(message))
            return True
        except Exception:
            self._remove_client(ws)
            return False

    def get_connected_devices(self) -> list[str]:
        """Get list of connected device IDs."""
        return list(self._devices.keys())


# REST API handlers for pairing
class RESTAPIHandler:
    """REST API for device pairing and status."""

    def __init__(self, authenticator: Authenticator, remote_server: JarvisRemoteServer):
        self._auth = authenticator
        self._server = remote_server
        self._app = None

    async def create_app(self):
        """Create aiohttp app for REST API."""
        try:
            from aiohttp import web
        except ImportError:
            logger.warning("aiohttp not installed, REST API unavailable")
            return None

        app = web.Application()

        # Pairing endpoints
        app.router.add_post("/api/pair", self.handle_pair)
        app.router.add_post("/api/confirm", self.handle_confirm)

        # Status endpoints
        app.router.add_get("/api/status", self.handle_status)
        app.router.add_get("/api/health", self.handle_health)

        # Device management (requires auth)
        app.router.add_get("/api/devices", self.handle_list_devices)
        app.router.add_delete("/api/devices/{device_id}", self.handle_revoke_device)

        self._app = app
        return app

    async def handle_pair(self, request):
        """Initiate device pairing."""
        try:
            data = await request.json()
            device_name = data.get("device_name", "Unknown Device")

            result = self._auth.initiate_pairing(device_name)
            return web.json_response(result)

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_confirm(self, request):
        """Confirm pairing and get credentials."""
        try:
            data = await request.json()
            token = data.get("token", "")

            result = self._auth.confirm_pairing(token)
            if not result:
                return web.json_response({"error": "Invalid or expired token"}, status=400)

            return web.json_response(result)

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_status(self, request):
        """Get server status."""
        return web.json_response({
            "status": "running",
            "connected_devices": len(self._server.get_connected_devices()),
            "version": "0.1.0",
        })

    async def handle_health(self, request):
        """Health check endpoint."""
        return web.json_response({"status": "healthy"})

    async def handle_list_devices(self, request):
        """List registered devices (requires auth)."""
        # Check auth header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response({"error": "Missing auth"}, status=401)

        token = auth_header[7:]
        result = self._auth.authenticate(token)
        if not result.success:
            return web.json_response({"error": result.error}, status=401)

        devices = self._auth.list_devices()
        return web.json_response({
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "created_at": d.created_at,
                    "last_seen": d.last_seen,
                    "is_active": d.is_active,
                }
                for d in devices
            ]
        })

    async def handle_revoke_device(self, request):
        """Revoke a device."""
        device_id = request.match_info["device_id"]

        # Check admin auth (simplified - use JWT from admin device)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response({"error": "Missing auth"}, status=401)

        token = auth_header[7:]
        result = self._auth.authenticate(token)
        if not result.success:
            return web.json_response({"error": result.error}, status=401)

        if self._auth.revoke_device(device_id):
            return web.json_response({"revoked": device_id})
        else:
            return web.json_response({"error": "Device not found"}, status=404)
