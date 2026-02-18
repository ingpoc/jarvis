"""A2A authentication: Bearer token validation."""
import secrets
from pathlib import Path

from jarvis.config import JARVIS_HOME


def get_token_path(configured_path: str = "") -> Path:
    """Get the path to the A2A token file."""
    if configured_path:
        return Path(configured_path)
    return JARVIS_HOME / "a2a_token"


def read_token(token_path: str = "") -> str | None:
    """Read the A2A token from file."""
    path = get_token_path(token_path)
    if not path.exists():
        return None
    try:
        return path.read_text().strip()
    except (OSError, PermissionError):
        return None


def validate_bearer_token(auth_header: str | None, token_path: str = "") -> bool:
    """Validate a Bearer token from Authorization header.

    Args:
        auth_header: The Authorization header value (e.g., "Bearer token123")
        token_path: Optional custom path to token file

    Returns:
        True if valid, False otherwise
    """
    if not auth_header:
        return False

    if not auth_header.startswith("Bearer "):
        return False

    provided_token = auth_header[7:]  # Strip "Bearer " prefix
    expected_token = read_token(token_path)

    if not expected_token:
        return False

    # Constant-time comparison to prevent timing attacks
    return secrets.compare_digest(provided_token, expected_token)


def generate_token() -> str:
    """Generate a new secure token."""
    import secrets
    return secrets.token_urlsafe(32)


def write_token(token: str, token_path: str = "") -> Path:
    """Write token to file."""
    path = get_token_path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token)
    # Restrict permissions
    path.chmod(0o600)
    return path
