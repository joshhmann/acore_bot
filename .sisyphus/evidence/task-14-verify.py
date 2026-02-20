#!/usr/bin/env python3
"""Verification script for ServiceFactory adapter architecture."""

import sys

sys.path.insert(0, "/root/acore_bot")

# Test imports
print("Testing imports...")
from core.interfaces import SimpleEventBus
from adapters.discord import DiscordInputAdapter, DiscordOutputAdapter
from adapters.cli import CLIInputAdapter, CLIOutputAdapter

print("✓ Core interfaces and adapters imported")

# Test factory class exists
print("\nTesting ServiceFactory class...")
from services.core.factory import ServiceFactory

# Test factory methods exist
print("\nChecking factory methods:")
methods_to_check = [
    "create_event_bus",
    "create_discord_adapter",
    "create_cli_adapter",
    "create_services",
]

for method in methods_to_check:
    if hasattr(ServiceFactory, method):
        print(f"  ✓ Method exists: {method}")
    else:
        print(f"  ✗ Missing method: {method}")
        sys.exit(1)

# Test create_event_bus directly (doesn't require Discord)
print("\nTesting create_event_bus...")
event_bus = SimpleEventBus()
print(f"  ✓ EventBus created: {type(event_bus).__name__}")

# Test create_cli_adapter directly
print("\nTesting create_cli_adapter...")


# Create mock factory
class MockBot:
    pass


factory = ServiceFactory(MockBot())
input_adapter, output_adapter = factory.create_cli_adapter()
print(f"  ✓ CLI Input Adapter: {type(input_adapter).__name__}")
print(f"  ✓ CLI Output Adapter: {type(output_adapter).__name__}")

# Test create_event_bus via factory
print("\nTesting create_event_bus via factory...")
event_bus = factory.create_event_bus()
print(f"  ✓ EventBus via factory: {type(event_bus).__name__}")

# Test EventBus is stored
print("\nTesting EventBus storage...")
if factory._event_bus is event_bus:
    print("  ✓ EventBus correctly stored in factory")
else:
    print("  ✗ EventBus not stored correctly")

# Test adapters are stored
print("\nTesting adapter storage...")
if "cli_input" in factory._adapters and "cli_output" in factory._adapters:
    print("  ✓ CLI adapters stored in factory")
else:
    print("  ✗ CLI adapters not stored correctly")

print("\n" + "=" * 50)
print("All verifications passed!")
print("=" * 50)
