# LLM-Agnostic Architecture & Anti-Hallucination Guide

## Goal
Make the bot work with ANY LLM under 8GB while preventing hallucinations through structured approaches.

---

## Anti-Hallucination Strategy

###  The Problem
LLMs hallucinate when asked about:
1. **Current time/dates** → "It's probably around 3 PM" ❌
2. **Math calculations** → "15% of 230 is about 34 or 35" ❌
3. **User-specific facts** → Invents user preferences ❌
4. **Recent events** → Makes up news ❌
5. **Precise conversions** → Estimates units ❌

### The Solution: Tools + Structured Output

**Instead of:**
```
User: "What time is it?"
LLM: "It's around 3 PM" ← HALLUCINATED
```

**Do this:**
```
User: "What time is it?"
LLM: TOOL: get_current_time()
System: [Executes tool] → "3:47 PM"
LLM: "It's 3:47 PM, mortal."
```

---

## Architecture for ANY LLM

### 1. LLM Adapter Pattern

```python
class LLMAdapter:
    """
    Abstract adapter - swap any LLM implementation.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 1.0,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Generate text completion."""
        raise NotImplementedError

    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system_prompt: str = "",
        **kwargs
    ) -> dict:
        """Generate structured output matching schema."""
        raise NotImplementedError

    def supports_structured_output(self) -> bool:
        """Check if model supports native structured output."""
        return False


class OllamaAdapter(LLMAdapter):
    """Adapter for Ollama models."""

    def __init__(self, model_name: str, host: str):
        self.model = model_name
        self.host = host
        self.client = ollama.AsyncClient(host=host)

    async def generate(self, prompt, system_prompt="", **kwargs):
        response = await self.client.generate(
            model=self.model,
            prompt=prompt,
            system=system_prompt,
            **kwargs
        )
        return response["response"]

    async def generate_structured(self, prompt, schema, system_prompt="", **kwargs):
        # Use JSON mode + validation
        json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema)}"

        response = await self.generate(
            prompt=json_prompt,
            system_prompt=system_prompt,
            options={"format": "json"},
            **kwargs
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON from response
            return self._extract_json(response)


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI-compatible APIs."""

    def __init__(self, model_name: str, api_key: str, base_url: str):
        self.model = model_name
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    def supports_structured_output(self) -> bool:
        return True  # GPT-4 supports function calling

    async def generate_structured(self, prompt, schema, system_prompt="", **kwargs):
        # Use native function calling
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            functions=[{
                "name": "respond",
                "parameters": schema
            }],
            function_call={"name": "respond"}
        )

        return json.loads(completion.choices[0].message.function_call.arguments)
```

---

## Recommended Models (<8GB)

### Tier 1: Best Anti-Hallucination

**1. Qwen2.5-7B-Instruct**
- Size: ~4.5GB (Q4_K_M)
- Strengths: Excellent reasoning, good tool use, strong instruction following
- Anti-hallucination: 9/10
- Speed: Fast
- Pull: `ollama pull qwen2.5:7b-instruct-q4_K_M`

**2. Gemma 2 9B-Instruct**
- Size: ~5.5GB (Q4_K_M)
- Strengths: Google model, very reliable, good structured output
- Anti-hallucination: 9/10
- Speed: Medium
- Pull: `ollama pull gemma2:9b-instruct-q4_K_M`

**3. Hermes-3-Llama-3.1-8B**
- Size: ~5GB (Q4_K_M)
- Strengths: Best function calling, strong tool use
- Anti-hallucination: 8.5/10
- Speed: Fast
- Pull: `ollama pull hermes3:8b-llama3.1-q4_K_M`

### Tier 2: Good Balance

**4. Llama 3.2-3B-Instruct**
- Size: ~2GB (Q4_K_M)
- Strengths: Very fast, efficient, decent reliability
- Anti-hallucination: 7/10
- Speed: Very fast
- Pull: `ollama pull llama3.2:3b-instruct-q4_K_M`

**5. Phi-4 (14B)**
- Size: ~8GB (Q4_K_M) - at the limit
- Strengths: Excellent reasoning from Microsoft
- Anti-hallucination: 9/10
- Speed: Slower
- Pull: `ollama pull phi4:14b-q4_K_M`

### Tier 3: Creative (Use with Caution)

**6. Stheno 3.2 (Current)**
- Size: ~7GB (Q4)
- Strengths: Very creative, excellent personality
- Anti-hallucination: 6/10 ⚠️
- Speed: Medium
- Note: More prone to creative hallucinations - NEEDS STRONG TOOL GUARDRAILS

---

## Configuration Per Model

### For Reliable Models (Qwen, Gemma, Hermes)

```python
MODEL_CONFIGS = {
    "qwen2.5:7b": {
        "temperature": 0.9,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "tool_usage": "native",
        "structured_output": True,
        "anti_hallucination_mode": "moderate"
    },
    "gemma2:9b": {
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 50,
        "repeat_penalty": 1.05,
        "tool_usage": "native",
        "structured_output": True,
        "anti_hallucination_mode": "moderate"
    }
}
```

### For Creative Models (Stheno, RP models)

```python
MODEL_CONFIGS = {
    "stheno-v3.2": {
        "temperature": 1.1,
        "min_p": 0.075,
        "top_k": 50,
        "repeat_penalty": 1.1,
        "tool_usage": "forced",  # Force tool use
        "structured_output": True,
        "anti_hallucination_mode": "aggressive",  # More guardrails
        "fact_check": True  # Double-check factual claims
    }
}
```

**Anti-Hallucination Modes:**

- **Moderate**: Add tool hints to system prompt, validate outputs
- **Aggressive**: Force tool use for facts, reject uncertain responses, require confidence scores

---

## System Prompt Structure

### Base Prompt (Model-Agnostic)

```python
BASE_PROMPT = """
{persona_description}

=== CRITICAL: ANTI-HALLUCINATION RULES ===

You MUST follow these rules to avoid hallucinating:

1. TIME & DATES: NEVER guess the time or date
   - Always use: TOOL: get_current_time() or TOOL: get_current_date()
   - ❌ NEVER: "It's around 3 PM"
   - ✅ ALWAYS: Use tool, then state result

2. MATH & CALCULATIONS: NEVER approximate
   - Always use: TOOL: calculate(expression="...")
   - ❌ NEVER: "About 34 or 35"
   - ✅ ALWAYS: Use tool for precise result

3. CONVERSIONS: NEVER estimate
   - Always use: TOOL: convert_temperature(...), convert_distance(...), etc.
   - ❌ NEVER: "Around 20 degrees Celsius"
   - ✅ ALWAYS: Use conversion tool

4. USER FACTS: NEVER invent
   - Always use: TOOL: get_user_profile(user_id=...)
   - ❌ NEVER: Make up preferences, past conversations
   - ✅ ALWAYS: Check database or admit you don't know

5. RECENT EVENTS: NEVER make up news
   - If uncertain: TOOL: search_web(query="...")
   - ❌ NEVER: Invent release dates, news, updates
   - ✅ ALWAYS: Search or admit uncertainty

6. UNCERTAINTY: ADMIT IT
   - If you don't know something → say so
   - If you're not confident → say so
   - ❌ NEVER: Make up facts to seem knowledgeable
   - ✅ ALWAYS: "I'm not sure" or "Let me search"

{tool_descriptions}

=== YOUR RESPONSE STYLE ===
{persona_style_guidelines}
"""
```

### Aggressive Mode (Creative Models)

```python
AGGRESSIVE_ANTI_HALLUCINATION = """
=== CRITICAL: YOU ARE IN STRICT FACT-CHECKING MODE ===

Before EVERY factual statement, ask yourself:
1. Am I 100% certain this is accurate?
2. Could this be time-sensitive information?
3. Should I use a tool to verify?

If ANY doubt → Use a tool or admit uncertainty.

Examples of FORBIDDEN responses:
❌ "It's probably around 3 PM"
❌ "I think that came out in 2023"
❌ "The answer is approximately 34"
❌ "Most users prefer..."
❌ "That game just released"

REQUIRED responses:
✅ TOOL: get_current_time() → "It's 3:47 PM"
✅ "I'm not sure when that released, let me search"
✅ TOOL: calculate(...) → "The answer is exactly 34.5"
✅ TOOL: get_user_profile(...) → Reference actual data
✅ TOOL: search_web(...) → Get current info

Your personality can be maintained while being factually rigorous.
"""
```

---

## Implementation Example

### Main Bot Class

```python
class AIFirstBot:
    """LLM-agnostic bot with anti-hallucination."""

    def __init__(self, model_config: dict):
        # Load model adapter
        self.llm = self._load_llm_adapter(model_config)

        # Load tools
        self.tools = EnhancedToolSystem()

        # Load persona
        self.persona = self._load_persona()

        # Set anti-hallucination mode
        self.anti_hallucination_mode = model_config.get(
            "anti_hallucination_mode",
            "moderate"
        )

    async def process_message(self, message: str, user_id: int, context: dict):
        """Process message with anti-hallucination measures."""

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # First pass: Generate with tools available
        response = await self.llm.generate(
            prompt=message,
            system_prompt=system_prompt,
            temperature=self.persona.get("temperature", 1.0)
        )

        # Check for tool calls
        tool_call = self.tools.parse_tool_call(response)

        if tool_call:
            # Execute tool
            tool_result = self.tools.execute_tool(
                tool_call["tool"],
                **tool_call["args"]
            )

            # Generate final response with tool result
            final_prompt = f"""
User message: {message}

You decided to use a tool:
Tool: {tool_call['tool']}
Result: {tool_result}

Now provide your final response incorporating this factual information.
Stay in character. Do not mention using a tool.
"""

            response = await self.llm.generate(
                prompt=final_prompt,
                system_prompt=system_prompt
            )

        # Aggressive mode: Validate response
        if self.anti_hallucination_mode == "aggressive":
            response = await self._validate_response(response, message)

        return response

    def _build_system_prompt(self) -> str:
        """Build complete system prompt."""

        base = self.persona.get("system_prompt", "")
        tools = self.tools.get_tool_descriptions()

        if self.anti_hallucination_mode == "aggressive":
            anti_halluc = AGGRESSIVE_ANTI_HALLUCINATION
        else:
            anti_halluc = "Use tools for factual information. Admit uncertainty."

        return f"{base}\n\n{tools}\n\n{anti_halluc}"

    async def _validate_response(self, response: str, original_message: str) -> str:
        """Validate response for potential hallucinations."""

        # Check for time references without tool use
        if any(word in response.lower() for word in ["time is", "it's", "o'clock"]):
            if "TOOL: get_current_time()" not in response:
                logger.warning("Possible time hallucination detected")
                # Re-generate with stronger prompt
                return await self._regenerate_with_tool_enforcement(original_message)

        # Check for math without tool use
        if any(word in original_message.lower() for word in ["calculate", "what's", "%", "percent"]):
            if "TOOL: calculate" not in response and any(char.isdigit() for char in response):
                logger.warning("Possible math hallucination detected")
                return await self._regenerate_with_tool_enforcement(original_message)

        return response
```

---

## Switching Models

### Easy Model Swap

```python
# .env file
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
ANTI_HALLUCINATION_MODE=moderate

# To switch:
# OLLAMA_MODEL=gemma2:9b-instruct-q4_K_M
# OLLAMA_MODEL=stheno-v3.2  # Use aggressive mode
```

### Model-Specific Configs

```python
# config.py
MODEL_CONFIGS = {
    "qwen2.5:7b": {
        "anti_hallucination": "moderate",
        "temperature": 0.9,
        "tool_enforcement": "hints"
    },
    "stheno-v3.2": {
        "anti_hallucination": "aggressive",
        "temperature": 1.1,
        "tool_enforcement": "strict",
        "fact_check": True
    },
    "gemma2:9b": {
        "anti_hallucination": "moderate",
        "temperature": 0.8,
        "tool_enforcement": "native"
    }
}
```

---

## Testing Anti-Hallucination

### Test Suite

```python
ANTI_HALLUCINATION_TESTS = [
    {
        "test": "Time query",
        "input": "What time is it?",
        "should_use_tool": True,
        "tool": "get_current_time",
        "should_not_contain": ["around", "probably", "approximately"]
    },
    {
        "test": "Math query",
        "input": "What's 15% of 230?",
        "should_use_tool": True,
        "tool": "calculate_percentage",
        "should_not_contain": ["about", "roughly", "~"]
    },
    {
        "test": "Conversion query",
        "input": "Convert 32F to Celsius",
        "should_use_tool": True,
        "tool": "convert_temperature",
        "should_not_contain": ["approximately", "around"]
    },
    {
        "test": "Recent events",
        "input": "What's new with Elden Ring?",
        "should_use_tool": True,
        "tool": "search_web",
        "acceptable_responses": ["Let me search", "I'm not sure"]
    }
]
```

---

## Summary: Anti-Hallucination Checklist

✅ **Tools for Facts**
- Time/dates → tools, never guessed
- Math → calculated, never approximated
- Conversions → precise, never estimated
- User facts → database, never invented

✅ **Structured Output**
- Use schemas for critical information
- Validate against expected formats
- Retry on invalid output

✅ **Confidence Awareness**
- LLM reports confidence
- Low confidence → search or admit
- Never fake confidence

✅ **Model-Specific Config**
- Reliable models → moderate guardrails
- Creative models → aggressive validation
- Tool enforcement level per model

✅ **Validation Pipeline**
- Check responses for hallucination patterns
- Re-generate with stronger prompts if needed
- Log and learn from failures

---

## Next Steps

1. **Choose your model** (Qwen 2.5 recommended for balance)
2. **Set anti-hallucination mode** based on model
3. **Test with the test suite** above
4. **Tune prompts** if hallucinations occur
5. **Monitor logs** for tool usage patterns

Would you like me to implement this LLM-agnostic system with your current Stheno model?
