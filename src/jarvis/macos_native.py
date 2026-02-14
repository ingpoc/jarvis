"""macOS native integrations: IOKit idle detection, Keychain, Core Spotlight, memory pressure.

All integrations use ctypes to call macOS frameworks directly from Python,
avoiding the need for PyObjC for these specific use cases.

Platform guard: Every function gracefully returns None/defaults on non-macOS.
This module is safe to import on any platform.
"""

import ctypes
import ctypes.util
import json
import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

IS_MACOS = platform.system() == "Darwin"
IS_APPLE_SILICON = IS_MACOS and platform.machine() == "arm64"

# ─── IOKit Idle Detection ───────────────────────────────────────────────────

_iokit = None
_cf = None
_iokit_loaded = False

if IS_MACOS:
    try:
        _iokit_path = ctypes.util.find_library("IOKit")
        _cf_path = ctypes.util.find_library("CoreFoundation")
        if _iokit_path and _cf_path:
            _iokit = ctypes.cdll.LoadLibrary(_iokit_path)
            _cf = ctypes.cdll.LoadLibrary(_cf_path)
            _iokit_loaded = True
    except Exception as e:
        logger.debug(f"IOKit load failed: {e}")


def get_idle_seconds() -> float | None:
    """Get system idle time in seconds using IOKit HID.

    Returns None on non-macOS or if IOKit is unavailable.
    Uses IOHIDSystem to read HIDIdleTime — the time since last
    keyboard/mouse/trackpad input.
    """
    if not _iokit_loaded:
        return None

    try:
        # IOServiceGetMatchingService(kIOMasterPortDefault, IOServiceMatching("IOHIDSystem"))
        _iokit.IOServiceMatching.restype = ctypes.c_void_p
        matching = _iokit.IOServiceMatching(b"IOHIDSystem")

        _iokit.IOServiceGetMatchingService.restype = ctypes.c_uint
        service = _iokit.IOServiceGetMatchingService(0, matching)

        if not service:
            return None

        # Create CFString for "HIDIdleTime"
        _cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        _cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32,
        ]
        key = _cf.CFStringCreateWithCString(None, b"HIDIdleTime", 0x08000100)  # kCFStringEncodingUTF8

        # IORegistryEntryCreateCFProperty
        _iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
        _iokit.IORegistryEntryCreateCFProperty.argtypes = [
            ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ]
        cf_number = _iokit.IORegistryEntryCreateCFProperty(service, key, None, 0)

        if cf_number:
            # Extract int64 from CFNumber
            idle_ns = ctypes.c_int64()
            _cf.CFNumberGetValue.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int64),
            ]
            _cf.CFNumberGetValue(cf_number, 4, ctypes.byref(idle_ns))  # 4 = kCFNumberSInt64Type
            _cf.CFRelease(cf_number)
            _cf.CFRelease(key)
            _iokit.IOObjectRelease(service)

            return idle_ns.value / 1_000_000_000.0  # ns -> seconds

        _cf.CFRelease(key)
        _iokit.IOObjectRelease(service)

    except Exception as e:
        logger.debug(f"IOKit idle time error: {e}")

    return None


# ─── Keychain Integration ───────────────────────────────────────────────────

def keychain_store(service: str, account: str, password: str) -> bool:
    """Store a credential in the macOS Keychain.

    Args:
        service: Service name (e.g., "com.jarvis.anthropic")
        account: Account name (e.g., "api_key")
        password: The secret value

    Returns:
        True if stored successfully
    """
    if not IS_MACOS:
        return False

    try:
        # Delete existing entry first (security add fails if it exists)
        subprocess.run(
            ["security", "delete-generic-password", "-s", service, "-a", account],
            capture_output=True,
        )
        result = subprocess.run(
            [
                "security", "add-generic-password",
                "-s", service,
                "-a", account,
                "-w", password,
                "-U",  # Update if exists
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info(f"Stored credential: {service}/{account}")
            return True
        else:
            logger.warning(f"Keychain store failed: {result.stderr}")
            return False
    except Exception as e:
        logger.warning(f"Keychain store error: {e}")
        return False


def keychain_retrieve(service: str, account: str) -> str | None:
    """Retrieve a credential from the macOS Keychain.

    Args:
        service: Service name (e.g., "com.jarvis.anthropic")
        account: Account name (e.g., "api_key")

    Returns:
        The secret value, or None if not found
    """
    if not IS_MACOS:
        return None

    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", service,
                "-a", account,
                "-w",  # Output password only
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.debug(f"Keychain retrieve error: {e}")
        return None


def keychain_delete(service: str, account: str) -> bool:
    """Delete a credential from the macOS Keychain."""
    if not IS_MACOS:
        return False

    try:
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", service, "-a", account],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


# ─── Core Spotlight / mdfind ────────────────────────────────────────────────

def spotlight_search(
    query: str,
    directory: str | None = None,
    max_results: int = 50,
    file_types: list[str] | None = None,
) -> list[str]:
    """Search for files using Core Spotlight (mdfind).

    This leverages macOS's indexed file search for near-instant results
    across the entire project, including content search.

    Args:
        query: Search query (supports Spotlight query syntax)
        directory: Limit search to this directory
        max_results: Maximum number of results
        file_types: Filter by file extensions (e.g., [".py", ".js"])

    Returns:
        List of matching file paths
    """
    if not IS_MACOS:
        return []

    try:
        cmd = ["mdfind"]

        # Scope to directory
        if directory:
            cmd.extend(["-onlyin", directory])

        # Build query with type filter
        if file_types:
            type_filter = " || ".join(
                f'kMDItemFSName == "*.{ext.lstrip(".")}"' for ext in file_types
            )
            query = f'({query}) && ({type_filter})'

        cmd.append(query)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
        )

        if result.returncode == 0:
            paths = [p for p in result.stdout.strip().splitlines() if p]
            return paths[:max_results]
        return []

    except subprocess.TimeoutExpired:
        logger.warning("Spotlight search timed out")
        return []
    except Exception as e:
        logger.debug(f"Spotlight search error: {e}")
        return []


def spotlight_search_code(
    pattern: str,
    directory: str,
    extensions: list[str] | None = None,
    max_results: int = 30,
) -> list[str]:
    """Search code files by content using Spotlight.

    Args:
        pattern: Text pattern to search for
        directory: Project directory to search in
        extensions: File extensions to include (default: common code files)

    Returns:
        List of file paths containing the pattern
    """
    if extensions is None:
        extensions = [".py", ".js", ".ts", ".rs", ".go", ".swift", ".java"]

    # Use kMDItemTextContent for content search
    query = f'kMDItemTextContent == "*{pattern}*"cd'
    return spotlight_search(query, directory, max_results, extensions)


def spotlight_index_project(directory: str) -> bool:
    """Request Spotlight to index a project directory.

    Tells mdimport to re-index the given path. Useful after
    cloning a new repo or creating many files.
    """
    if not IS_MACOS:
        return False

    try:
        result = subprocess.run(
            ["mdimport", directory],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Requested Spotlight indexing for: {directory}")
            return True
        return False
    except Exception as e:
        logger.debug(f"Spotlight index error: {e}")
        return False


# ─── Memory Pressure Detection ──────────────────────────────────────────────

def get_memory_pressure() -> dict[str, Any] | None:
    """Get system memory pressure level using macOS memory_pressure tool.

    Returns dict with 'level' (normal/warn/critical) and memory stats,
    or None on non-macOS.
    """
    if not IS_MACOS:
        return None

    try:
        result = subprocess.run(
            ["memory_pressure"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout + result.stderr

        # Parse the output
        level = "normal"
        if "CRITICAL" in output.upper():
            level = "critical"
        elif "WARN" in output.upper():
            level = "warn"

        # Also get vm_stat for detailed numbers
        vm_result = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5,
        )
        free_pages = 0
        active_pages = 0
        page_size = 16384  # M4 uses 16K pages

        for line in vm_result.stdout.splitlines():
            if "free:" in line.lower():
                try:
                    free_pages = int(line.split(":")[1].strip().rstrip("."))
                except ValueError:
                    pass
            elif "active:" in line.lower():
                try:
                    active_pages = int(line.split(":")[1].strip().rstrip("."))
                except ValueError:
                    pass
            elif "page size" in line.lower():
                try:
                    page_size = int(line.split(":")[1].strip().rstrip("."))
                except ValueError:
                    pass

        free_mb = (free_pages * page_size) / (1024 * 1024)
        active_mb = (active_pages * page_size) / (1024 * 1024)

        return {
            "level": level,
            "free_mb": round(free_mb, 1),
            "active_mb": round(active_mb, 1),
            "should_hibernate": level == "critical",
        }

    except Exception as e:
        logger.debug(f"Memory pressure check error: {e}")
        return None


# ─── Thermal Pressure ───────────────────────────────────────────────────────

def get_thermal_pressure() -> str | None:
    """Get thermal pressure level.

    Returns 'nominal', 'moderate', 'heavy', 'critical', or None.
    """
    if not IS_MACOS:
        return None

    try:
        result = subprocess.run(
            ["pmset", "-g", "therm"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.lower()
        if "critical" in output:
            return "critical"
        if "heavy" in output:
            return "heavy"
        if "moderate" in output:
            return "moderate"
        return "nominal"
    except Exception:
        return None


# ─── System Info ─────────────────────────────────────────────────────────────

def get_apple_silicon_info() -> dict[str, Any] | None:
    """Get Apple Silicon chip information.

    Returns chip model, core counts, memory, Neural Engine info.
    """
    if not IS_APPLE_SILICON:
        return None

    try:
        result = subprocess.run(
            ["sysctl", "-a"],
            capture_output=True, text=True, timeout=5,
        )
        info: dict[str, Any] = {"chip": "unknown", "total_memory_gb": 0}

        for line in result.stdout.splitlines():
            if "machdep.cpu.brand_string" in line:
                info["chip"] = line.split(":")[1].strip()
            elif "hw.memsize" in line:
                try:
                    bytes_val = int(line.split(":")[1].strip())
                    info["total_memory_gb"] = round(bytes_val / (1024 ** 3), 1)
                except ValueError:
                    pass
            elif "hw.perflevel0.physicalcpu" in line:
                try:
                    info["performance_cores"] = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif "hw.perflevel1.physicalcpu" in line:
                try:
                    info["efficiency_cores"] = int(line.split(":")[1].strip())
                except ValueError:
                    pass

        # Get GPU core count via system_profiler
        sp_result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True, text=True, timeout=10,
        )
        if sp_result.returncode == 0:
            try:
                sp_data = json.loads(sp_result.stdout)
                displays = sp_data.get("SPDisplaysDataType", [])
                if displays:
                    gpu_info = displays[0]
                    info["gpu_cores"] = gpu_info.get("sppci_cores", "unknown")
                    info["gpu_model"] = gpu_info.get("sppci_model", "unknown")
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

        return info

    except Exception as e:
        logger.debug(f"Apple Silicon info error: {e}")
        return None


def get_neural_engine_available() -> bool:
    """Check if Neural Engine is available (for Foundation Models)."""
    if not IS_APPLE_SILICON:
        return False

    try:
        # All M-series chips have Neural Engine
        result = subprocess.run(
            ["sysctl", "hw.optional.arm.FEAT_ANE"],
            capture_output=True, text=True, timeout=5,
        )
        return "1" in result.stdout
    except Exception:
        # Fallback: all M4 chips have ANE
        return IS_APPLE_SILICON


# ─── Platform Summary ────────────────────────────────────────────────────────

def get_platform_capabilities() -> dict[str, Any]:
    """Get a summary of all macOS-specific capabilities available."""
    return {
        "is_macos": IS_MACOS,
        "is_apple_silicon": IS_APPLE_SILICON,
        "iokit_available": _iokit_loaded,
        "keychain_available": IS_MACOS,
        "spotlight_available": IS_MACOS,
        "neural_engine": get_neural_engine_available(),
        "chip_info": get_apple_silicon_info(),
        "memory_pressure": get_memory_pressure(),
        "thermal_pressure": get_thermal_pressure(),
    }
