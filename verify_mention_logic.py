"""Test script for mention handling logic."""
import sys
import re
from typing import List


class MockMember:
    """Mock Discord member for testing."""
    
    def __init__(self, id: int, name: str, display_name: str, bot: bool = False):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.bot = bot


class MockGuild:
    """Mock Discord guild for testing."""
    
    def __init__(self, members: List[MockMember]):
        self.members = members


def _restore_mentions(content: str, guild: MockGuild) -> str:
    """Convert @Username mentions back to <@user_id> for Discord.
    
    This ensures that when the LLM outputs @Username, it gets converted to
    a proper Discord mention tag that is clickable.
    
    Args:
        content: Message content with @Username mentions
        guild: Discord guild to get member list from
        
    Returns:
        Content with @Username replaced by <@user_id>
    """
    if not guild or not content:
        return content
        
    # Get all members and sort by name length (descending) to prevent partial matches
    # e.g., "Rob" inside "Robert"
    members = sorted(guild.members, key=lambda m: len(m.display_name), reverse=True)
    
    for member in members:
        # Skip bots
        if member.bot:
            continue
            
        # Try display name first (server nickname)
        display_name = member.display_name
        content = content.replace(f"@{display_name}", f"<@{member.id}>")
        
        # Also try global username if different from display name
        if member.name != display_name:
            content = content.replace(f"@{member.name}", f"<@{member.id}>")
            
    return content


def _clean_for_tts(content: str, guild: MockGuild) -> str:
    """Clean content for TTS by replacing mentions with natural names.
    
    This ensures that TTS pronounces "Username" instead of reading out
    "less than at one two three four five..."
    
    Args:
        content: Message content with <@user_id> or @Username mentions
        guild: Discord guild to get member list from
        
    Returns:
        Content with mentions replaced by natural names
    """
    if not guild or not content:
        return content
        
    # First, replace <@user_id> with display names
    for member in guild.members:
        # Skip bots
        if member.bot:
            continue
            
        # Replace <@ID> with display name
        mention_pattern = f"<@{member.id}>"
        content = content.replace(mention_pattern, member.display_name)
        
        # Also handle <@!ID> format (mobile mentions)
        mention_pattern_mobile = f"<@!{member.id}>"
        content = content.replace(mention_pattern_mobile, member.display_name)
    
    # Second, remove @ symbols from any remaining @Username patterns
    # This handles cases where LLM outputs @Username
    content = re.sub(r'@([A-Za-z0-9_]+)', r'\1', content)
    
    return content


def test_restore_mentions():
    """Test _restore_mentions with various username patterns."""
    print("Testing _restore_mentions...")
    
    # Create mock guild with members
    members = [
        MockMember(123456789, "blobert", "Blobert"),
        MockMember(987654321, "robert", "Robert"),
        MockMember(111222333, "rob", "Rob"),
        MockMember(444555666, "testuser", "Test User"),
    ]
    guild = MockGuild(members)
    
    # Test cases
    test_cases = [
        ("Hey @Blobert, how are you?", "Hey <@123456789>, how are you?"),
        ("@Robert and @Rob are here", "<@987654321> and <@111222333> are here"),
        ("Hello @Test User!", "Hello <@444555666>!"),
        # Test partial match prevention (should match Robert before Rob)
        ("@Robert is not @Rob", "<@987654321> is not <@111222333>"),
        # Test with no mentions
        ("No mentions here", "No mentions here"),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected in test_cases:
        result = _restore_mentions(input_text, guild)
        if result == expected:
            print(f"✓ PASS: '{input_text}' -> '{result}'")
            passed += 1
        else:
            print(f"✗ FAIL: '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{result}'")
            failed += 1
    
    print(f"\n_restore_mentions: {passed} passed, {failed} failed\n")
    return failed == 0


def test_clean_for_tts():
    """Test _clean_for_tts with ID mentions and @mentions."""
    print("Testing _clean_for_tts...")
    
    # Create mock guild with members
    members = [
        MockMember(123456789, "blobert", "Blobert"),
        MockMember(987654321, "robert", "Robert"),
        MockMember(111222333, "rob", "Rob"),
        MockMember(444555666, "testuser", "Test User"),
    ]
    guild = MockGuild(members)
    
    # Test cases
    test_cases = [
        # Test <@ID> format
        ("Hey <@123456789>, how are you?", "Hey Blobert, how are you?"),
        ("<@987654321> and <@111222333> are here", "Robert and Rob are here"),
        # Test <@!ID> format (mobile)
        ("Hello <@!444555666>!", "Hello Test User!"),
        # Test @Username format
        ("Hey @Blobert, nice to see you!", "Hey Blobert, nice to see you!"),
        ("@Robert is here", "Robert is here"),
        # Test mixed formats
        ("Hey <@123456789> and @Robert!", "Hey Blobert and Robert!"),
        # Test with no mentions
        ("No mentions here", "No mentions here"),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected in test_cases:
        result = _clean_for_tts(input_text, guild)
        if result == expected:
            print(f"✓ PASS: '{input_text}' -> '{result}'")
            passed += 1
        else:
            print(f"✗ FAIL: '{input_text}'")
            print(f"  Expected: '{expected}'")
            print(f"  Got:      '{result}'")
            failed += 1
    
    print(f"\n_clean_for_tts: {passed} passed, {failed} failed\n")
    return failed == 0


def test_round_trip():
    """Test that the conversions work correctly in both directions."""
    print("Testing round-trip conversions...")
    
    # Create mock guild with members
    members = [
        MockMember(123456789, "blobert", "Blobert"),
        MockMember(987654321, "robert", "Robert"),
    ]
    guild = MockGuild(members)
    
    # Test LLM output -> Discord -> TTS
    llm_output = "Hey @Blobert, @Robert wants to talk to you!"
    
    # Convert for Discord (should have clickable mentions)
    discord_version = _restore_mentions(llm_output, guild)
    expected_discord = "Hey <@123456789>, <@987654321> wants to talk to you!"
    
    # Convert for TTS (should have natural names)
    tts_version = _clean_for_tts(llm_output, guild)
    expected_tts = "Hey Blobert, Robert wants to talk to you!"
    
    # Also test TTS from Discord version
    tts_from_discord = _clean_for_tts(discord_version, guild)
    
    print(f"LLM Output:      '{llm_output}'")
    print(f"Discord Version: '{discord_version}'")
    print(f"TTS Version:     '{tts_version}'")
    print(f"TTS from Discord: '{tts_from_discord}'")
    
    success = True
    if discord_version != expected_discord:
        print(f"✗ FAIL: Discord version incorrect")
        print(f"  Expected: '{expected_discord}'")
        success = False
    else:
        print(f"✓ PASS: Discord version correct")
    
    if tts_version != expected_tts:
        print(f"✗ FAIL: TTS version incorrect")
        print(f"  Expected: '{expected_tts}'")
        success = False
    else:
        print(f"✓ PASS: TTS version correct")
    
    if tts_from_discord != expected_tts:
        print(f"✗ FAIL: TTS from Discord version incorrect")
        print(f"  Expected: '{expected_tts}'")
        success = False
    else:
        print(f"✓ PASS: TTS from Discord version correct")
    
    print()
    return success


if __name__ == "__main__":
    print("=" * 60)
    print("User Mention Tagging Test Suite")
    print("=" * 60)
    print()
    
    all_passed = True
    all_passed &= test_restore_mentions()
    all_passed &= test_clean_for_tts()
    all_passed &= test_round_trip()
    
    print("=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
