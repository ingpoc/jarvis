"""Tests for jarvis.macos_native — macOS-specific integrations.

These tests work on all platforms. macOS-specific features return
None/False gracefully on non-macOS.
"""

import platform

import pytest

from jarvis.macos_native import (
    IS_APPLE_SILICON,
    IS_MACOS,
    get_apple_silicon_info,
    get_idle_seconds,
    get_memory_pressure,
    get_neural_engine_available,
    get_platform_capabilities,
    get_thermal_pressure,
    keychain_delete,
    keychain_retrieve,
    keychain_store,
    spotlight_index_project,
    spotlight_search,
    spotlight_search_code,
)


class TestPlatformGuards:
    """Test that all functions have proper platform guards."""

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_idle_seconds_none_on_linux(self):
        assert get_idle_seconds() is None

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_keychain_store_fails_on_linux(self):
        assert keychain_store("test", "test", "test") is False

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_keychain_retrieve_none_on_linux(self):
        assert keychain_retrieve("test", "test") is None

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_keychain_delete_fails_on_linux(self):
        assert keychain_delete("test", "test") is False

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_spotlight_empty_on_linux(self):
        assert spotlight_search("test") == []

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_spotlight_code_empty_on_linux(self):
        assert spotlight_search_code("class Foo", "/tmp") == []

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_spotlight_index_fails_on_linux(self):
        assert spotlight_index_project("/tmp") is False

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_memory_pressure_none_on_linux(self):
        assert get_memory_pressure() is None

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_thermal_pressure_none_on_linux(self):
        assert get_thermal_pressure() is None

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_chip_info_none_on_linux(self):
        assert get_apple_silicon_info() is None

    @pytest.mark.skipif(IS_MACOS, reason="Testing non-macOS behavior")
    def test_neural_engine_false_on_linux(self):
        assert get_neural_engine_available() is False


class TestPlatformCapabilities:
    """Test platform capability summary."""

    def test_capabilities_returns_dict(self):
        caps = get_platform_capabilities()
        assert isinstance(caps, dict)
        assert "is_macos" in caps
        assert "is_apple_silicon" in caps
        assert "iokit_available" in caps
        assert "keychain_available" in caps
        assert "spotlight_available" in caps
        assert "neural_engine" in caps

    def test_capabilities_consistent(self):
        caps = get_platform_capabilities()
        if not caps["is_macos"]:
            assert caps["is_apple_silicon"] is False
            assert caps["iokit_available"] is False
            assert caps["keychain_available"] is False


class TestMacOSFeatures:
    """Tests that only run on actual macOS hardware."""

    @pytest.mark.skipif(not IS_MACOS, reason="Requires macOS")
    def test_idle_seconds_returns_float(self):
        result = get_idle_seconds()
        # May be None if IOKit fails, but if it works it should be a float
        if result is not None:
            assert isinstance(result, float)
            assert result >= 0

    @pytest.mark.skipif(not IS_MACOS, reason="Requires macOS")
    def test_memory_pressure_returns_dict(self):
        result = get_memory_pressure()
        if result is not None:
            assert "level" in result
            assert result["level"] in ("normal", "warn", "critical")
            assert "free_mb" in result

    @pytest.mark.skipif(not IS_MACOS, reason="Requires macOS")
    def test_thermal_pressure_returns_string(self):
        result = get_thermal_pressure()
        if result is not None:
            assert result in ("nominal", "moderate", "heavy", "critical")

    @pytest.mark.skipif(not IS_APPLE_SILICON, reason="Requires Apple Silicon")
    def test_chip_info(self):
        info = get_apple_silicon_info()
        assert info is not None
        assert "chip" in info
        assert "total_memory_gb" in info
        assert info["total_memory_gb"] > 0

    @pytest.mark.skipif(not IS_APPLE_SILICON, reason="Requires Apple Silicon")
    def test_neural_engine(self):
        assert get_neural_engine_available() is True

    @pytest.mark.skipif(not IS_MACOS, reason="Requires macOS")
    def test_spotlight_search_finds_system_files(self):
        # Search for a file that definitely exists on macOS
        results = spotlight_search("kMDItemFSName == 'hosts'", "/etc")
        # /etc/hosts should be found
        assert any("hosts" in r for r in results)

    @pytest.mark.skipif(not IS_MACOS, reason="Requires macOS")
    def test_keychain_roundtrip(self):
        service = "com.jarvis.test-only"
        account = "test-key"
        password = "test-value-12345"

        # Store
        assert keychain_store(service, account, password) is True

        # Retrieve
        result = keychain_retrieve(service, account)
        assert result == password

        # Delete
        assert keychain_delete(service, account) is True

        # Verify deleted
        assert keychain_retrieve(service, account) is None
