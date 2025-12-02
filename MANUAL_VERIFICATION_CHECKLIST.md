# Manual Verification Checklist

## Prerequisites
- [ ] Bot is running
- [ ] You have access to a Discord server with the bot
- [ ] You have at least one other user to test mentions with
- [ ] Bot has permissions to join voice channels (for TTS testing)

## Test 1: Text Tagging Verification

### Setup
1. [ ] Open a text channel where the bot can respond
2. [ ] Have another user available (or use an alt account)

### Test Steps
1. [ ] Send a message to the bot: "Hey bot, say hello to @OtherUser"
2. [ ] Wait for bot response

### Expected Results
- [ ] Bot's response contains a **blue clickable mention** (not plain text)
- [ ] Clicking the mention opens the user's profile
- [ ] The mention format is `<@user_id>` in the raw message (right-click → Copy Message Link to verify)

### Example
```
User:    "Hey Dagoth, say hello to @Blobert"
Bot:     "Greetings, @Blobert!" ← This should be a blue clickable tag
```

## Test 2: TTS Audio Verification

### Setup
1. [ ] Join a voice channel
2. [ ] Ensure bot is in the same voice channel (or will auto-join)
3. [ ] Ensure `AUTO_REPLY_WITH_VOICE` is enabled in config

### Test Steps
1. [ ] Send a message to the bot: "Hey bot, greet @OtherUser"
2. [ ] Wait for bot to respond with audio

### Expected Results
- [ ] Bot speaks the response in voice channel
- [ ] Audio says "OtherUser" or "Other User" (natural pronunciation)
- [ ] Audio does **NOT** say "less than at one two three four..." or read out numbers
- [ ] Audio does **NOT** say "at OtherUser" (@ symbol should be removed)

### Example
```
User:    "Hey Dagoth, say hello to @Blobert"
Bot TTS: "Greetings, Blobert!" ← Should sound natural
         NOT: "Greetings, at Blobert!"
         NOT: "Greetings, less than at one two three..."
```

## Test 3: Multiple Mentions

### Test Steps
1. [ ] Send: "Hey bot, @User1 and @User2 are both awesome"
2. [ ] Check text response has clickable mentions for both users
3. [ ] Check TTS pronounces both names naturally

### Expected Results
- [ ] Text: Both mentions are blue and clickable
- [ ] TTS: Both names pronounced naturally without @ or IDs

## Test 4: Edge Cases

### Test 4a: Partial Name Matches
If you have users named "Rob" and "Robert":
1. [ ] Send: "Hey bot, tell @Robert something"
2. [ ] Verify bot mentions the correct user (Robert, not Rob)

### Test 4b: Display Names vs Usernames
If a user has a different display name (server nickname):
1. [ ] Send: "Hey bot, greet @DisplayName"
2. [ ] Verify bot correctly identifies and mentions the user

### Test 4c: No Mentions
1. [ ] Send: "Hey bot, how are you?"
2. [ ] Verify bot responds normally without errors

## Test 5: Streaming Responses (if enabled)

### Setup
1. [ ] Ensure `RESPONSE_STREAMING_ENABLED = True` in config
2. [ ] Use slash command `/chat` for easier testing

### Test Steps
1. [ ] Use `/chat` command: "Say hello to @OtherUser"
2. [ ] Watch the response stream in

### Expected Results
- [ ] Intermediate updates show proper mentions (blue tags)
- [ ] Final message has proper mentions
- [ ] No duplicate messages

## Troubleshooting

### Issue: Mentions are plain text (not clickable)
**Possible Causes:**
- `_restore_mentions()` not being called
- Guild context is None (check if in DMs vs server)
- User not found in guild members

**Debug:**
- Check bot logs for errors
- Verify the user is actually in the server
- Check if `discord_response` is being used for sending

### Issue: TTS reads out user IDs
**Possible Causes:**
- `_clean_for_tts()` not being called
- `tts_response` not being passed to `_speak_response_in_voice()`

**Debug:**
- Check bot logs for TTS generation
- Verify `tts_response` is created correctly
- Check if guild context is available

### Issue: Bot crashes when mentioning users
**Possible Causes:**
- Guild members not loaded
- Permission issues

**Debug:**
- Check bot logs for exceptions
- Verify bot has proper intents enabled (GUILD_MEMBERS)
- Check if guild.members is populated

## Success Criteria

✅ **All tests pass if:**
1. Text mentions are blue and clickable
2. TTS pronounces names naturally
3. No errors in bot logs
4. Works with multiple mentions
5. Works with streaming responses
6. Handles edge cases correctly

## Notes

- Test with different users to ensure name matching works correctly
- Test in different channels to ensure consistency
- If using RVC voice conversion, verify it doesn't affect mention pronunciation
- Check chat history to ensure mentions are stored correctly
