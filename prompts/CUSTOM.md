# Creating Custom Prompts

Create your own bot personality by making a new `.txt` file in this directory!

## Quick Start

1. Create a new file: `prompts/your_name.txt`
2. Write your system prompt
3. Update `.env`:
   ```env
   SYSTEM_PROMPT_FILE=./prompts/your_name.txt
   ```
4. Restart the bot

## Prompt Writing Tips

### Structure

```
[Who the bot is]
You are a [personality] AI assistant...

[Personality traits]
Your characteristics:
- Trait 1
- Trait 2
- Trait 3

[Communication style]
How you communicate:
- Style point 1
- Style point 2

[Special instructions]
Remember to:
- Instruction 1
- Instruction 2
```

### What Makes a Good Prompt

✅ **Do:**
- Be specific about personality
- Define tone and style clearly
- Give examples of desired behavior
- Set boundaries (what NOT to do)
- Include formatting preferences
- Define the bot's role

❌ **Don't:**
- Make it too long (keep under 500 words)
- Use contradictory instructions
- Be too restrictive (allow flexibility)
- Forget about Discord context

### Examples by Use Case

#### For Gaming Communities
```
You are [Character Name], the [role] of this gaming guild.
- Use gaming terminology
- Hype up achievements
- Share strategies
- Keep it fun and competitive
```

#### For Learning/Education
```
You are a patient teacher and mentor.
- Break down complex topics
- Use analogies and examples
- Encourage questions
- Adapt to skill levels
```

#### For Creative Communities
```
You are an inspiring creative companion.
- Encourage experimentation
- Provide constructive feedback
- Share creative techniques
- Celebrate unique ideas
```

#### For Support/Help Desk
```
You are a professional support specialist.
- Be patient and understanding
- Provide step-by-step solutions
- Ask clarifying questions
- Follow up on issues
```

## Advanced: Dynamic Prompts

You can also set the prompt directly in `.env` for quick changes:

```env
SYSTEM_PROMPT="You are a sarcastic but helpful AI. Keep responses witty and clever."
```

This overrides the prompt file.

## Testing Your Prompt

After creating a custom prompt:

1. Restart the bot
2. Use `/chat` to test
3. Check if responses match your intended personality
4. Iterate and refine

## Prompt Variables

You can reference these in your prompts:
- Discord markdown for formatting
- User context (the bot knows it's in Discord)
- Voice capabilities (if enabled)

## Community Prompts

Share your best prompts! Some ideas:
- `dungeon_master.txt` - D&D game master
- `therapist.txt` - Supportive listener
- `coach.txt` - Motivational coach
- `comedian.txt` - Humor-focused
- `scientist.txt` - Technical/scientific
- `storyteller.txt` - Creative narratives
- `translator.txt` - Language helper
- `news_anchor.txt` - News delivery style

## Need Inspiration?

Check the included prompts:
- `default.txt` - Basic helpful assistant
- `friendly.txt` - Casual and warm
- `professional.txt` - Business/formal
- `gaming.txt` - Gaming community
- `pirate.txt` - Fun pirate character

Mix and match ideas from these to create your perfect bot personality!

Happy prompting! 🤖✨
