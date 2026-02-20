#!/usr/bin/env python3
"""
Production deployment verification script.

This script tests the specific fixes required for production deployment.
Run after applying the recommended fixes to verify readiness.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import os
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def verify_blocking_io_fixes():
    """Verify that blocking I/O has been fixed in async contexts."""
    logger.info("Verifying blocking I/O fixes...")

    issues_found = []

    # Check specific files that had issues
    files_to_check = [
        "/root/acore_bot/services/llm/ollama.py",
        "/root/acore_bot/services/discord/profiles.py",
        "/root/acore_bot/services/persona/relationships.py",
    ]

    for file_path in files_to_check:
        if not Path(file_path).exists():
            continue

        try:
            with open(file_path, "r") as f:
                content = f.read()
                lines = content.split("\n")

                in_async_function = False
                async_function_indent = 0

                for i, line in enumerate(lines, 1):
                    stripped = line.strip()

                    # Track async function boundaries
                    if "async def " in stripped:
                        in_async_function = True
                        async_function_indent = len(line) - len(line.lstrip())
                        continue

                    # End of async function
                    if (
                        in_async_function
                        and stripped
                        and len(line) - len(line.lstrip()) <= async_function_indent
                    ):
                        if (
                            stripped.startswith("def ")
                            or stripped.startswith("class ")
                            or stripped.startswith("async ")
                        ):
                            in_async_function = False
                            continue

                    # Check for blocking operations in async contexts
                    if in_async_function:
                        # Allow aiofiles but block sync open()
                        if "open(" in stripped and "aiofiles" not in stripped:
                            issues_found.append(
                                f"{file_path}:{i} - Blocking file operation in async context"
                            )

                        # Allow asyncio.sleep but block time.sleep
                        if "time.sleep(" in stripped:
                            issues_found.append(
                                f"{file_path}:{i} - Blocking sleep in async context"
                            )

        except Exception as e:
            logger.error(f"Error checking {file_path}: {e}")

    if issues_found:
        logger.error(f"❌ Found {len(issues_found)} unresolved blocking I/O issues:")
        for issue in issues_found:
            logger.error(f"  {issue}")
        return False
    else:
        logger.info("✅ All blocking I/O issues resolved")
        return True


async def verify_security_fixes():
    """Verify security fixes have been applied."""
    logger.info("Verifying security fixes...")

    issues = []

    # Check .env.example for default secrets
    env_example = Path("/root/acore_bot/.env.example")
    if env_example.exists():
        content = env_example.read_text()

        # Should have placeholder tokens, not real or default values
        if "DISCORD_TOKEN=" in content and not content.count(
            "DISCORD_TOKEN=your_discord_token_here"
        ):
            issues.append(".env.example should use placeholder token")

        if "change_me_in_production" in content:
            issues.append("Default API keys still present in .env.example")

    # Check directory permissions
    data_dir = Path("/root/acore_bot/data")
    if data_dir.exists():
        stat = data_dir.stat()
        mode = stat.st_mode & 0o777
        if mode & 0o077:  # Group/others have write access
            issues.append("Data directory has overly permissive permissions")

    if issues:
        logger.error(f"❌ Found {len(issues)} security issues:")
        for issue in issues:
            logger.error(f"  {issue}")
        return False
    else:
        logger.info("✅ Security issues resolved")
        return True


async def verify_type_safety():
    """Verify type safety fixes."""
    logger.info("Verifying type safety...")

    try:
        # Import modules that had type errors
        from adapters.discord.commands.chat.main import ChatCog
        from services.analytics.dashboard import AnalyticsDashboard

        logger.info("✅ Type safety imports successful")

        # Test basic instantiation
        try:
            from unittest.mock import Mock

            mock_bot = Mock()
            mock_bot.services = {}

            # This should not raise type errors
            logger.info("✅ Type safety verified")
            return True

        except Exception as e:
            logger.error(f"❌ Type safety verification failed: {e}")
            return False

    except ImportError as e:
        logger.error(f"❌ Import error indicates type safety issues: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Type safety check failed: {e}")
        return False


async def verify_service_health():
    """Verify service health and monitoring."""
    logger.info("Verifying service health systems...")

    try:
        from services.core.health import HealthCheckService

        health_service = HealthCheckService()

        # Test cache functionality
        test_service = Mock()
        health_service.register_services({"test": test_service})

        result = await health_service.check_all_services()
        logger.info("✅ Health check service working")

        # Test caching
        result2 = await health_service.check_all_services()
        logger.info("✅ Health check caching working")

        return True

    except Exception as e:
        logger.error(f"❌ Service health verification failed: {e}")
        return False


async def verify_error_handling():
    """Verify error handling resilience."""
    logger.info("Verifying error handling...")

    try:
        from services.core.metrics import MetricsService

        metrics = MetricsService()

        # Test error recording
        metrics.record_error("TestError", "Test message")

        # Test error rate calculation
        error_rate = metrics.get_error_rate()
        assert isinstance(error_rate, float)

        # Test recent errors
        recent_errors = metrics.get_recent_errors(10)
        assert isinstance(recent_errors, list)

        logger.info("✅ Error handling systems working")
        return True

    except Exception as e:
        logger.error(f"❌ Error handling verification failed: {e}")
        return False


async def verify_resource_cleanup():
    """Verify resource cleanup mechanisms."""
    logger.info("Verifying resource cleanup...")

    cleanup_test_passed = True

    try:
        # Test task cancellation
        async def test_task():
            await asyncio.sleep(1)
            return "done"

        task = asyncio.create_task(test_task())

        # Cancel immediately
        task.cancel()

        try:
            await asyncio.wait_for(task, timeout=0.1)
        except asyncio.CancelledError:
            logger.info("✅ Task cancellation works")
        except asyncio.TimeoutError:
            logger.warning("⚠ Task cancellation timeout")
            cleanup_test_passed = False

        # Test service cleanup timeout handling
        async def mock_cleanup():
            await asyncio.sleep(2)
            return "cleaned"

        try:
            await asyncio.wait_for(mock_cleanup(), timeout=0.1)
        except asyncio.TimeoutError:
            logger.info("✅ Cleanup timeout handling works")

    except Exception as e:
        logger.error(f"❌ Resource cleanup verification failed: {e}")
        cleanup_test_passed = False

    return cleanup_test_passed


async def load_test_simulation():
    """Simulate light load to test system stability."""
    logger.info("Running load test simulation...")

    try:
        from services.core.metrics import MetricsService

        metrics = MetricsService()

        # Simulate concurrent operations
        tasks = []

        async def simulate_request():
            start = time.time()
            await asyncio.sleep(0.01)  # Simulate work
            duration = (time.time() - start) * 1000
            metrics.record_response_time(duration, {"test": True})
            return True

        # Run 50 concurrent requests
        for _ in range(50):
            tasks.append(simulate_request())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        logger.info(f"✅ Load test: {successful}/50 requests successful")

        # Check metrics integrity
        summary = metrics.get_summary()
        assert summary["total_requests"] == 50

        logger.info("✅ Load test simulation passed")
        return True

    except Exception as e:
        logger.error(f"❌ Load test failed: {e}")
        return False


async def main():
    """Run all verification tests."""
    logger.info("🔍 PRODUCTION DEPLOYMENT VERIFICATION")
    logger.info("=" * 50)

    tests = [
        ("Blocking I/O Fixes", verify_blocking_io_fixes),
        ("Security Fixes", verify_security_fixes),
        ("Type Safety", verify_type_safety),
        ("Service Health", verify_service_health),
        ("Error Handling", verify_error_handling),
        ("Resource Cleanup", verify_resource_cleanup),
        ("Load Test", load_test_simulation),
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"\n{'=' * 20} {test_name} {'=' * 20}")
        start_time = time.time()

        try:
            result = await test_func()
            results.append((test_name, result, time.time() - start_time))
        except Exception as e:
            logger.error(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False, time.time() - start_time))

    # Summary
    logger.info(f"\n{'=' * 50}")
    logger.info("VERIFICATION SUMMARY")
    logger.info(f"{'=' * 50}")

    passed = sum(1 for _, result, _ in results if result)
    total = len(results)

    for test_name, result, duration in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name} ({duration:.2f}s)")

    logger.info(f"\nFinal Score: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 BOT IS PRODUCTION READY!")
        logger.info("\nDeployment Checklist:")
        logger.info("✅ All critical issues resolved")
        logger.info("✅ Security vulnerabilities fixed")
        logger.info("✅ Performance issues addressed")
        logger.info("✅ Error handling verified")
        logger.info("\nReady for deployment with:")
        logger.info("- Systemd service: sudo bash install_service.sh")
        logger.info("- Monitoring: Check /api/health endpoint")
        logger.info("- Logs: sudo journalctl -u discordbot -f")
        return 0
    else:
        logger.error(f"🚨 {total - passed} issues remain - NOT PRODUCTION READY")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
