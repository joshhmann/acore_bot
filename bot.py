# bot_modal.py
import os, re, time, asyncio, base64, io, json
from typing import Optional, Any
from collections import defaultdict, deque
from urllib.parse import urlparse
import discord
import html 
from discord import app_commands
from discord.ui import Modal, TextInput
from dotenv import load_dotenv
import requests
from utils import json_load, json_save_atomic, chunk_text, send_ephemeral, send_long_ephemeral, send_long_reply
from utils.formatter import normalize_ratio, wrap_response
from utils.intent import classify as classify_intent
from soap import SoapClient
from ollama import OllamaClient
from rag_store import RagStore
from arliai import ArliaiClient
from ac_db import DBConfig as ACDBConfig, get_online_count as db_get_online_count, get_totals as db_get_totals
from bot.tools import get_current_time

load_dotenv()
import ac_metrics as kpi
from commands.kpi import setup_kpi as setup_kpi_commands
from bot.tools import SLUM_QUERY_TOOL, run_named_query
from commands.health import setup_health as setup_health_commands

TOKEN = os.getenv("DISCORD_TOKEN")
SOAP_HOST = os.getenv("SOAP_HOST", "127.0.0.1")
SOAP_PORT = int(os.getenv("SOAP_PORT", "7878"))
SOAP_USER = os.getenv("SOAP_USER")
SOAP_PASS = os.getenv("SOAP_PASS")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", "0"))
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID", "0"))
STATUS_POLL_SECONDS = int(os.getenv("STATUS_POLL_SECONDS", "30"))
SERVER_INFO_FILE = os.getenv("SERVER_INFO_FILE", "server_info.json")
CHAT_HISTORY_FILE = os.getenv("CHAT_HISTORY_FILE", "chat_history.json")
KB_FILE = os.getenv("KB_FILE", "kb.json")
DOCS_DIR = os.getenv("DOCS_DIR", "docs")

# Optional: Ollama integration
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() in {"1","true","yes","on"}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_AUTO_REPLY = os.getenv("OLLAMA_AUTO_REPLY", "false").lower() in {"1","true","yes","on"}
OLLAMA_SYSTEM_PROMPT = os.getenv(
    "OLLAMA_SYSTEM_PROMPT",
    (
        "You are WowSlumsBot, a concise, friendly assistant focused on AzerothCore, "
        "World of Warcraft private server operations, and helpful Discord chat. "
        "Answer briefly (<= 4 sentences) unless asked for details. "
        "For economy, player, guild, auction, faction, or arena questions, call the "
        "appropriate tool instead of guessing. When discussing WotLK mechanics, cite "
        "relevant documentation."
    ),
)
OLLAMA_HISTORY_TURNS = int(os.getenv("OLLAMA_HISTORY_TURNS", "50"))
OLLAMA_VISION_ENABLED = os.getenv("OLLAMA_VISION_ENABLED", "false").lower() in {"1","true","yes","on"}
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
try:
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
except Exception:
    OLLAMA_TEMPERATURE = 0.7
OLLAMA_TOOLS_ENABLED = os.getenv("OLLAMA_TOOLS_ENABLED", "true").lower() in {"1","true","yes","on"}
OLLAMA_TOOLS_ROLE = os.getenv("OLLAMA_TOOLS_ROLE", "").strip()

# Optional: Retrieval-Augmented Generation (use local KB/server info as context)
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in {"1","true","yes","on"}
RAG_TOPK = int(os.getenv("RAG_TOPK", "3"))
RAG_MAX_CHARS = int(os.getenv("RAG_MAX_CHARS", "3000"))
RAG_MIN_SCORE = int(os.getenv("RAG_MIN_SCORE", "10"))
RAG_IN_AUTOREPLY = os.getenv("RAG_IN_AUTOREPLY", "false").lower() in {"1","true","yes","on"}
KB_SUGGEST_IN_CHAT = os.getenv("KB_SUGGEST_IN_CHAT", "false").lower() in {"1","true","yes","on"}
METRICS_STRICT = os.getenv("METRICS_STRICT", "true").lower() in {"1","true","yes","on"}

# Arliai (optional)
ARLIAI_ENABLED = os.getenv("ARLIAI_ENABLED", "false").lower() in {"1","true","yes","on"}
ARLIAI_API_KEY = os.getenv("ARLIAI_API_KEY", "")
ARLIAI_TEXT_API_KEY = os.getenv("ARLIAI_TEXT_API_KEY", "")
ARLIAI_IMAGE_API_KEY = os.getenv("ARLIAI_IMAGE_API_KEY", "")
ARLIAI_BASE_URL = os.getenv("ARLIAI_BASE_URL", "https://api.arliai.com")
ARLIAI_TEXT_MODEL = os.getenv("ARLIAI_TEXT_MODEL", "TEXT_GENERATION_MODEL")
ARLIAI_IMAGE_MODEL = os.getenv("ARLIAI_IMAGE_MODEL", "IMAGE_GENERATION_MODEL")

# Provider-agnostic LLM settings (DRY)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()  # ollama|arliai
LLM_TEXT_MODEL = os.getenv("LLM_TEXT_MODEL", "") or (ARLIAI_TEXT_MODEL if LLM_PROVIDER == "arliai" else OLLAMA_MODEL)
LLM_IMAGE_MODEL = os.getenv("LLM_IMAGE_MODEL", "") or (ARLIAI_IMAGE_MODEL if LLM_PROVIDER == "arliai" else "")
LLM_HOST = os.getenv("LLM_HOST", "") or (ARLIAI_BASE_URL if LLM_PROVIDER == "arliai" else OLLAMA_HOST)
LLM_API_KEY = os.getenv("LLM_API_KEY", "") or (ARLIAI_API_KEY if LLM_PROVIDER == "arliai" else "")
LLM_CONTEXT_TOKENS = int(os.getenv("LLM_CONTEXT_TOKENS", "0"))  # optional hint
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", str(OLLAMA_NUM_PREDICT)))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
try:
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
except Exception:
    OLLAMA_TEMPERATURE = 0.7

# Optional: public info to answer FAQs
REALMLIST_HOST = os.getenv("REALMLIST_HOST", "set realmlist logon.yourserver.com")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://yourserver.com")
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "")
SUPPORT_URL = os.getenv("SUPPORT_URL", "")
XP_RATE = os.getenv("XP_RATE", "")
QUEST_XP_RATE = os.getenv("QUEST_XP_RATE", "")
DROP_RATE = os.getenv("DROP_RATE", "")
GOLD_RATE = os.getenv("GOLD_RATE", "")
HONOR_RATE = os.getenv("HONOR_RATE", "")
REPUTATION_RATE = os.getenv("REPUTATION_RATE", "")
PROFESSION_RATE = os.getenv("PROFESSION_RATE", "")
BOTS_SOAP_COMMAND = os.getenv("BOTS_SOAP_COMMAND", "")
BOTS_PARSE_REGEX = os.getenv("BOTS_PARSE_REGEX", "")
DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() in {"1","true","yes","on"}
DB_HOST = os.getenv("DB_HOST", "192.168.0.80")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "acbot_ro")
DB_PASS = os.getenv("DB_PASS", "CHANGE_ME")
DB_AUTH_DB = os.getenv("DB_AUTH_DB", "auth")
DB_CHAR_DB = os.getenv("DB_CHAR_DB", "characters")
DB_WORLD_DB = os.getenv("DB_WORLD_DB", "world")

def _db_cfg() -> Optional[ACDBConfig]:
    if not DB_ENABLED or not DB_USER:
        return None
    return ACDBConfig(DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_AUTH_DB, DB_CHAR_DB, DB_WORLD_DB)

USER_QPS = (1, 3)  # 1 request per 3 seconds
CHANNEL_QPS = (5, 10)  # 5 requests per 10 seconds

_user_calls: dict[int, deque[float]] = defaultdict(deque)
_channel_calls: dict[int, deque[float]] = defaultdict(deque)

def _qps_check(user_id: int, channel_id: int | None, *, update: bool = True) -> tuple[bool, float, str]:
    now = time.time()
    dq_u = _user_calls[user_id]
    while dq_u and now - dq_u[0] > USER_QPS[1]:
        dq_u.popleft()
    if len(dq_u) >= USER_QPS[0]:
        wait = USER_QPS[1] - (now - dq_u[0])
        return False, wait, "user"
    dq_c = None
    if channel_id is not None:
        dq_c = _channel_calls[channel_id]
        while dq_c and now - dq_c[0] > CHANNEL_QPS[1]:
            dq_c.popleft()
        if len(dq_c) >= CHANNEL_QPS[0]:
            wait = CHANNEL_QPS[1] - (now - dq_c[0])
            return False, wait, "channel"
    if update:
        dq_u.append(now)
        if dq_c is not None:
            dq_c.append(now)
    return True, 0.0, ""

def ratelimit(user_id: int, channel_id: int | None = None) -> bool:
    ok, _, _ = _qps_check(user_id, channel_id, update=True)
    return ok

def seconds_until_allowed(user_id: int, channel_id: int | None = None) -> int:
    ok, wait, _ = _qps_check(user_id, channel_id, update=False)
    if ok:
        return 0
    return int(wait + 0.999)

def valid_username(u: str) -> bool:
    return 3 <= len(u) <= 16 and re.fullmatch(r"[A-Za-z0-9_\-]+", u) is not None

def valid_password(p: str) -> bool:
    return 6 <= len(p) <= 32

def soap_execute(command: str, timeout: float = 6.0) -> str:
    url = f"http://{SOAP_HOST}:{SOAP_PORT}/"
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="urn:AC">
  <SOAP-ENV:Body>
    <ns1:executeCommand>
      <command>{command}</command>
    </ns1:executeCommand>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'''.encode("utf-8")
    auth = base64.b64encode(f"{SOAP_USER}:{SOAP_PASS}".encode()).decode()
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "Authorization": f"Basic {auth}",
    }
    r = requests.post(url, data=envelope, headers=headers, timeout=timeout)
    r.raise_for_status()
    # Accept both <return> and <result>, and unescape entities like &#xD;
    m = re.search(r"<(?:return|result)[^>]*>(.*?)</(?:return|result)>", r.text, re.S | re.I)
    if m:
        return html.unescape(m.group(1)).strip()
    # Fallback: strip tags if schema differs
    text = re.sub(r"<[^>]+>", "", r.text)
    return html.unescape(text).strip()

soap = SoapClient(SOAP_HOST, SOAP_PORT, SOAP_USER, SOAP_PASS)

async def run_soap(cmd: str) -> str:
    return await soap.run(cmd)

def format_soap_error(e: Exception) -> str:
    return soap.format_error(e)

"""Utility helpers moved to utils.py"""

def _has_tools_role_member(member) -> bool:
    if not OLLAMA_TOOLS_ROLE:
        return False
    try:
        return any(getattr(r, "name", "").lower() == OLLAMA_TOOLS_ROLE.lower() for r in getattr(member, "roles", []))
    except Exception:
        return False

def _has_tools_role(inter: discord.Interaction) -> bool:
    return _has_tools_role_member(getattr(inter, "user", None))

def require_allowed(inter: discord.Interaction) -> bool:
    if not ((ALLOWED_GUILD_ID == 0) or (inter.guild and inter.guild.id == ALLOWED_GUILD_ID)):
        return False
    if not ((ALLOWED_CHANNEL_ID == 0) or (inter.channel and inter.channel.id == ALLOWED_CHANNEL_ID) or _has_tools_role(inter)):
        # Channel restricted; attempt to notify
        try:
            # Note: function may be called before a response is created
            # Use send_ephemeral for safety
            import asyncio as _a
            _a.create_task(send_ephemeral(inter, "🔒 Use this command in the designated channel or with the required role."))
        except Exception:
            pass
        return False
    return True

def enforce_ratelimit_inter(inter: discord.Interaction) -> bool:
    uid = inter.user.id if inter.user else 0
    cid = inter.channel.id if inter.channel else None
    ok, wait, scope = _qps_check(uid, cid, update=True)
    if not ok:
        try:
            msg = f"⏳ Please wait {int(wait)+1}s."
            if scope == "channel":
                msg = f"⏳ Channel busy. Retry in {int(wait)+1}s."
            import asyncio as _a
            _a.create_task(send_ephemeral(inter, msg))
        except Exception:
            pass
        return False
    return True

"""Chunking + long send helpers are imported"""

# ---- Ollama helpers ----
ollama_client = OllamaClient(OLLAMA_HOST, OLLAMA_MODEL, num_predict=OLLAMA_NUM_PREDICT, temperature=OLLAMA_TEMPERATURE)
OLLAMA_TOOLS = [SLUM_QUERY_TOOL]

def ollama_available() -> bool:
    return OLLAMA_ENABLED and ollama_client.available

def ollama_chat(prompt: str, timeout: float = 15.0, system: Optional[str] = None, history: Optional[list[dict]] = None, images: Optional[list[bytes]] = None) -> str:
    return ollama_client.chat(prompt, timeout=timeout, system=system, history=history, images=images)

def format_ollama_error(e: Exception) -> str:
    return ollama_client.format_error(e)

arliai_client: Optional[ArliaiClient] = None
if ARLIAI_ENABLED and (ARLIAI_API_KEY or ARLIAI_TEXT_API_KEY or ARLIAI_IMAGE_API_KEY):
    try:
        arliai_client = ArliaiClient(ARLIAI_API_KEY, base_url=ARLIAI_BASE_URL, text_api_key=(ARLIAI_TEXT_API_KEY or ARLIAI_API_KEY), image_api_key=(ARLIAI_IMAGE_API_KEY or ARLIAI_API_KEY))
    except Exception:
        arliai_client = None

# Tool registry for LLM providers
LLM_TOOLS = {"get_current_time": get_current_time}

def llm_available() -> bool:
    if LLM_PROVIDER == "ollama":
        return OLLAMA_ENABLED and ollama_available()
    if LLM_PROVIDER == "arliai":
        return ARLIAI_ENABLED and bool(arliai_client)
    return False

def llm_chat(prompt: str, *, system: Optional[str], history: Optional[list[dict]], images: Optional[list[bytes]] = None) -> str:
    if LLM_PROVIDER == "ollama":
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        user_msg: dict = {"role": "user", "content": prompt}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)
        data = ollama_client.chat_raw(messages, tools=OLLAMA_TOOLS, timeout=20.0)
        msg = data.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        while tool_calls:
            messages.append(msg)
            for call in tool_calls:
                fn = call.get("function", {})
                fname = fn.get("name")
                args_s = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args_s)
                except Exception:
                    args = {}
                result: Any
                if fname == "slum_query":
                    qname = args.get("name")
                    qparams = args.get("params", {}) if isinstance(args.get("params"), dict) else {}
                    try:
                        result = asyncio.run(run_named_query(qname, qparams))
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"unknown function {fname}"}
                messages.append({
                    "role": "tool",
                    "name": fname,
                    "tool_call_id": call.get("id"),
                    "content": json.dumps(result, default=str),
                })
            data = ollama_client.chat_raw(messages, tools=OLLAMA_TOOLS, timeout=20.0)
            msg = data.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
        return str(msg.get("content") or data.get("response") or "").strip()
    if LLM_PROVIDER == "arliai":
        if not arliai_client:
            raise RuntimeError("Arliai client not available")
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        if history:
            for m in history:
                role = m.get("role")
                content = m.get("content", "")
                if role in {"user", "assistant", "system"} and content:
                    msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": prompt})
        data = arliai_client.chat(LLM_TEXT_MODEL or ARLIAI_TEXT_MODEL, msgs, temperature=OLLAMA_TEMPERATURE, max_tokens=OLLAMA_NUM_PREDICT)
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message") or {}
                text = msg.get("content")
                if text:
                    return str(text)
        return str(data)
    raise RuntimeError(f"Unknown LLM provider: {LLM_PROVIDER}")

def format_llm_error(e: Exception) -> str:
    if LLM_PROVIDER == "arliai":
        from arliai import ArliaiClient as _C
        return _C.format_error(e)
    return format_ollama_error(e)


def _is_realm_health_query(text: str) -> bool:
    s = (text or "").lower()
    keys = [
        "realm", "server", "population", "online", "busy", "alive", "dead",
        "how's the realm", "how is the realm", "anyone online", "players online",
    ]
    return any(k in s for k in keys)

def _is_numeric_query(text: str) -> bool:
    s = (text or "").lower()
    return ("how many" in s) or ("how much" in s) or ("count" in s) or ("number of" in s)

def _matches(s: str, *subs: str) -> bool:
    s = s.lower()
    return any(x in s for x in subs)

def _is_rates_query(s: str) -> bool:
    return _matches(s, "xp rate", "rates", "xp rates", "drop rate", "gold rate", "honor rate", "reputation rate", "profession rate")


def _is_time_query(text: str) -> bool:
    s = (text or "").lower()
    return any(k in s for k in ("what time", "time is it", "current time", "time now"))

class RegisterModal(Modal, title="Create Game Account"):
    username: TextInput = TextInput(label="Username", placeholder="3–16 chars: A–Z a–z 0–9 _ -", min_length=3, max_length=16)
    password: TextInput = TextInput(label="Password", style=discord.TextStyle.paragraph, placeholder="6–32 chars", min_length=6, max_length=32)

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Rate limit & validate
        cid = interaction.channel.id if interaction.channel else None
        if not ratelimit(self._user_id, cid):
            wait = seconds_until_allowed(self._user_id, cid)
            return await interaction.response.send_message(f"⏳ Please wait {wait}s before trying again.", ephemeral=True)

        u = str(self.username.value).strip()
        p = str(self.password.value).strip()
        if not valid_username(u):
            return await interaction.response.send_message("❌ Username must be 3–16 chars (A–Z, a–z, 0–9, _ , -).", ephemeral=True)
        if not valid_password(p):
            return await interaction.response.send_message("❌ Password must be 6–32 chars.", ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            out = await run_soap(f".account create {u} {p}")
            ok = ("created" in out.lower()) or ("success" in out.lower())
            msg = f"{'✅' if ok else '⚠️'} Result for `{u}`:\n```\n{out[:1800]}\n```"
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {format_soap_error(e)}", ephemeral=True)

def parse_server_info(raw: str) -> dict:
    """
    Parse common fields from .server info output.
    Returns keys: version, connected, characters, peak, uptime, update_mean, update_p95, update_p99, update_max
    """
    s = raw.replace("\r", "\n")  # in case &#xD; already unescaped
    out = {}

    # Version/build line
    m = re.search(r"^AzerothCore\s+rev\.\s+(.+)$", s, re.MULTILINE)
    if m: out["version"] = m.group(1).strip()

    # Connected players & characters in world
    m = re.search(r"Connected players:\s*(\d+).*?Characters in world:\s*(\d+)", s, re.I | re.S)
    if m:
        out["connected"] = int(m.group(1))
        out["characters"] = int(m.group(2))

    # Connection peak
    m = re.search(r"Connection peak:\s*(\d+)", s, re.I)
    if m: out["peak"] = int(m.group(1))

    # Uptime
    m = re.search(r"Server uptime:\s*([^\n\r]+)", s, re.I)
    if m: out["uptime"] = m.group(1).strip()

    # Update time diffs
    m = re.search(r"Mean:\s*(\d+)ms", s, re.I)
    if m: out["update_mean"] = int(m.group(1))
    m = re.search(r"Percentiles\s*\(95,\s*99,\s*max\):\s*(\d+)ms,\s*(\d+)ms,\s*(\d+)ms", s, re.I)
    if m:
        out["update_p95"] = int(m.group(1))
        out["update_p99"] = int(m.group(2))
        out["update_max"] = int(m.group(3))

    return out

def format_quick_status(info: dict | None) -> str:
    if not info:
        return "🔴 Server is OFFLINE or unreachable."
    pieces = []
    if (c := info.get("connected")) is not None:
        pieces.append(f"🟢 Online: {c} players")
    if (u := info.get("uptime")):
        pieces.append(f"Uptime: {u}")
    if (v := info.get("version")):
        pieces.append(f"Build: {v}")
    return " | ".join(pieces) if pieces else "🟢 Server is ONLINE"

def get_connect_instructions() -> str:
    realmlist = info_get("realmlist", REALMLIST_HOST)
    website = info_get("website", WEBSITE_URL)
    download = info_get("download", DOWNLOAD_URL)
    support = info_get("support", SUPPORT_URL)
    lines = [
        "How to connect:",
        f"- Realmlist: `{realmlist}`",
    ]
    if download:
        lines.append(f"- Client download: {download}")
    if website:
        lines.append(f"- Website: {website}")
    if support:
        lines.append(f"- Support: {support}")
    return "\n".join(lines)

def get_rates_lines() -> list[str]:
    # Prefer server_info.json 'rates' dict if present
    rates = info_get("rates", {}) or {}
    lines: list[str] = []
    def add(k_env: str, label: str):
        val = rates.get(label.lower()) if isinstance(rates, dict) else None
        if not val:
            val = globals().get(k_env, "")
        if val:
            lines.append(f"- {label}: {normalize_ratio(val)}")
    add("XP_RATE", "XP")
    add("QUEST_XP_RATE", "Quest XP")
    add("DROP_RATE", "Drop")
    add("GOLD_RATE", "Gold")
    add("HONOR_RATE", "Honor")
    add("REPUTATION_RATE", "Reputation")
    add("PROFESSION_RATE", "Profession")
    return lines

_bots_cache: dict[str, tuple[float, str]] = {}

async def get_bots_status() -> str:
    key = "bots"
    now = time.time()
    # 30s cache
    if key in _bots_cache and (now - _bots_cache[key][0] < 30):
        return _bots_cache[key][1]
    if not BOTS_SOAP_COMMAND:
        return "(no bots command configured)"
    try:
        out = await run_soap(BOTS_SOAP_COMMAND)
        if BOTS_PARSE_REGEX:
            m = re.search(BOTS_PARSE_REGEX, out, re.I)
            if m:
                out_fmt = f"Bots online: {m.group(1)}"
            else:
                out_fmt = out.strip()[:200]
        else:
            out_fmt = out.strip()[:200]
        _bots_cache[key] = (now, out_fmt)
        return out_fmt
    except Exception as e:
        return f"(bots query failed: {e})"

def get_help_overview() -> str:
    lines = [
        "Commands:",
        "- /wowstatus — Show server status (embed)",
        "- /wowregister — Create a game account (private modal)",
        "- /wowchangepass — Change a game password (private modal)",
        "- /wowonline — Show online player count",
        "- /wowrates — Show server rates",
        "- /wowbots — Show bot status (if configured)",
    ]
    # Hide image understanding when not supported
    if not (LLM_PROVIDER == "ollama" and OLLAMA_VISION_ENABLED):
        try:
            lines.remove("- /wowaskimg — Ask about an image")
        except ValueError:
            pass
    return "\n".join(lines)

def info_get(key: str, default: str | None = None):
    try:
        data = getattr(bot, "_info", None) or {}
        val = data.get(key)
        return val if (val is not None and val != "") else default
    except Exception:
        return default


class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()  # slash cmds don't need message_content
        if OLLAMA_ENABLED and OLLAMA_AUTO_REPLY:
            intents.message_content = True  # required to read channel messages
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._status_task: Optional[asyncio.Task] = None
        self._server_online_last: Optional[bool] = None
        # Ollama chat context (per-channel)
        self._chat_hist: dict[int, list[dict]] = {}
        # Optional per-guild system prompt override
        self._system_prompt_override: dict[int, str] = {}
        # Info file data
        self._info: dict = {}
        # Knowledge base entries (moved to RagStore)
        self._kb: list[dict] = []
        # Curated documents (chunked) (moved to RagStore)
        self._docs: list[dict] = []
        # History file path
        self._history_file: str = CHAT_HISTORY_FILE
        # RAG enable override per guild
        self._rag_override: dict[int, bool] = {}
        # Auto-reply override per guild
        self._auto_reply_override: dict[int, bool] = {}

    async def setup_hook(self):
        # If you restrict to a single guild, register commands there for instant availability
        # Provider-dependent: hide unsupported commands before sync
        try:
            if LLM_PROVIDER != "ollama" or not OLLAMA_VISION_ENABLED:
                self.tree.remove_command("wowaskimg")
            if LLM_PROVIDER != "arliai":
                self.tree.remove_command("wowimage")
                self.tree.remove_command("wowupscale")
            if not OLLAMA_TOOLS_ENABLED:
                for name in (
                    "wowask",
                    "wowimage",
                    "wowupscale",
                    "wowaskimg",
                    "wowascii",
                    "wowpersona_set",
                    "wowpersona_show",
                    "wowclearhistory",
                    "wowrag_on",
                    "wowrag_off",
                    "wowrag_show",
                    "wowautoreply_on",
                    "wowautoreply_off",
                    "wowautoreply_show",
                    "wowllminfo",
                ):
                    self.tree.remove_command(name)
        except Exception:
            pass

        # Register KPI commands (DB-driven metrics) only if DB is enabled
        if DB_ENABLED and DB_USER:
            setup_kpi_commands(self.tree)

        # Health check command available always
        setup_health_commands(self.tree)

        if ALLOWED_GUILD_ID:
            guild = discord.Object(id=ALLOWED_GUILD_ID)
            # Copy globals (including KPI commands registered above) to guild for instant availability
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

        # Start background server status poller
        if self._status_task is None:
            self._status_task = asyncio.create_task(self._status_poller())

        # Load info file (non-fatal if missing)
        try:
            self._load_info_file()
        except Exception:
            pass

        # Load chat history/personas (non-fatal if missing)
        try:
            self._load_history_file()
        except Exception:
            pass

        # Load RAG store (KB + Docs)
        try:
            self._rag = RagStore(KB_FILE, DOCS_DIR)
            self._rag.load_all()
        except Exception:
            self._rag = RagStore(KB_FILE, DOCS_DIR)

    def _load_info_file(self) -> None:
        path = SERVER_INFO_FILE
        if not path:
            return
        try:
            data = json_load(path, {})
            if isinstance(data, dict):
                self._info = data
        except FileNotFoundError:
            # ignore if not present
            self._info = {}
        except Exception:
            # leave old info on parse error
            raise

    def _load_history_file(self) -> None:
        path = self._history_file
        if not path:
            return
        try:
            data = json_load(path, {})
            if isinstance(data, dict):
                hist = data.get("history") or {}
                if isinstance(hist, dict):
                    # keys may be strings, convert to int where possible
                    self._chat_hist = {}
                    for k, v in hist.items():
                        try:
                            cid = int(k)
                        except Exception:
                            continue
                        if isinstance(v, list):
                            # ensure shape
                            msgs = []
                            for m in v:
                                if isinstance(m, dict) and "role" in m and "content" in m:
                                    msgs.append({"role": str(m["role"]), "content": str(m["content"])})
                            self._chat_hist[cid] = msgs
                personas = data.get("personas") or {}
                if isinstance(personas, dict):
                    self._system_prompt_override = {}
                    for k, v in personas.items():
                        try:
                            gid = int(k)
                        except Exception:
                            continue
                        if isinstance(v, str):
                            self._system_prompt_override[gid] = v
                settings = data.get("settings") or {}
                if isinstance(settings, dict):
                    ar = settings.get("auto_reply") or {}
                    if isinstance(ar, dict):
                        self._auto_reply_override = {}
                        for k, v in ar.items():
                            try:
                                gid = int(k)
                            except Exception:
                                continue
                            if isinstance(v, bool):
                                self._auto_reply_override[gid] = v
                    ragen = settings.get("rag_enabled") or {}
                    if isinstance(ragen, dict):
                        self._rag_override = {}
                        for k, v in ragen.items():
                            try:
                                gid = int(k)
                            except Exception:
                                continue
                            if isinstance(v, bool):
                                self._rag_override[gid] = v
        except FileNotFoundError:
            # ignore if not present
            return
        except Exception:
            raise

    def _save_history_file(self) -> None:
        path = self._history_file
        if not path:
            return
        try:
            data = {
                "history": {str(k): v for k, v in (self._chat_hist or {}).items()},
                "personas": {str(k): v for k, v in (self._system_prompt_override or {}).items()},
                "settings": {
                    "auto_reply": {str(k): v for k, v in (self._auto_reply_override or {}).items()},
                    "rag_enabled": {str(k): v for k, v in (self._rag_override or {}).items()},
                }
            }
            json_save_atomic(path, data)
        except Exception:
            # do not raise during runtime
            pass



    async def _status_poller(self):
        await self.wait_until_ready()
        while not self.is_closed():
            online = False
            connected = None
            parsed = {}
            try:
                out = await run_soap(".server info")
                info = parse_server_info(out)
                online = True
                connected = info.get("connected")
                parsed = info
            except Exception:
                online = False

            # Update presence
            try:
                if online:
                    name = f"AzerothCore: Online"
                    if isinstance(connected, int):
                        name = f"AzerothCore: {connected} online"
                    activity = discord.Activity(type=discord.ActivityType.watching, name=name)
                    await self.change_presence(status=discord.Status.online, activity=activity)
                else:
                    activity = discord.Activity(type=discord.ActivityType.watching, name="AzerothCore: Offline")
                    await self.change_presence(status=discord.Status.do_not_disturb, activity=activity)
            except Exception:
                pass

            # Notify on state change
            try:
                if self._server_online_last is None:
                    self._server_online_last = online
                elif online != self._server_online_last:
                    self._server_online_last = online
                    channel = await self._get_notify_channel()
                    if channel:
                        if online:
                            msg = "🟢 SLUMS WOW is ONLINE"
                            if isinstance(connected, int):
                                msg += f" ({connected} players)"
                        else:
                            msg = "🔴 Slums WOW is OFFLINE"
                        try:
                            await channel.send(msg)
                        except Exception:
                            pass
            except Exception:
                pass

            # (metrics collection disabled)

            await asyncio.sleep(max(5, STATUS_POLL_SECONDS))

    async def _get_notify_channel(self) -> Optional[discord.abc.Messageable]:
        # Prefer explicit allowed channel
        if ALLOWED_CHANNEL_ID:
            ch = self.get_channel(ALLOWED_CHANNEL_ID)
            if isinstance(ch, (discord.TextChannel, discord.Thread)):
                return ch
        # Otherwise try first text channel in allowed guild
        if ALLOWED_GUILD_ID:
            guild = self.get_guild(ALLOWED_GUILD_ID)
            if guild:
                for ch in guild.text_channels:
                    perms = ch.permissions_for(guild.me)
                    if perms.send_messages:
                        return ch
        # Fallback: any guild, any text channel where we can talk
        for guild in self.guilds:
            for ch in guild.text_channels:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages:
                    return ch
        return None

    def _get_system_prompt(self, guild_id: Optional[int]) -> str:
        if guild_id and guild_id in self._system_prompt_override:
            return self._system_prompt_override[guild_id]
        return OLLAMA_SYSTEM_PROMPT

    def _auto_reply_enabled(self, guild_id: Optional[int]) -> bool:
        if guild_id and guild_id in self._auto_reply_override:
            return bool(self._auto_reply_override[guild_id])
        return bool(OLLAMA_AUTO_REPLY)

    def _rag_enabled(self, guild_id: Optional[int]) -> bool:
        if guild_id and guild_id in self._rag_override:
            return bool(self._rag_override[guild_id])
        return bool(RAG_IN_AUTOREPLY)

    def _build_rag_system(self, query: str, guild_id: Optional[int]) -> str:
        base = self._get_system_prompt(guild_id)
        if not RAG_ENABLED:
            return base
        pieces: list[str] = []
        # KB hits (with score threshold)
        try:
            if getattr(self, "_rag", None) and self._rag.kb and query:
                scored = self._rag.search_kb(query, limit=max(1, RAG_TOPK), return_scores=True)
                for score, h in scored:
                    if score < RAG_MIN_SCORE:
                        continue
                    title = h.get("title", "")
                    text = (h.get("text", "") or "").strip()
                    if text:
                        pieces.append(f"KB: {title}\n{text}")
        except Exception:
            pass
        # Curated docs hits (with score threshold)
        try:
            if getattr(self, "_rag", None) and self._rag.docs and query and RAG_TOPK > 0:
                scored = self._rag.search_docs(query, limit=RAG_TOPK, return_scores=True)
                for score, h in scored:
                    if score < RAG_MIN_SCORE:
                        continue
                    title = h.get("title", "")
                    text = (h.get("text", "") or "").strip()
                    if text:
                        pieces.append(f"DOC: {title}\n{text}")
        except Exception:
            pass
        # Server info highlights
        try:
            realmlist = info_get("realmlist", REALMLIST_HOST)
            website = info_get("website", WEBSITE_URL)
            download = info_get("download", DOWNLOAD_URL)
            support = info_get("support", SUPPORT_URL)
            rates = get_rates_lines()
            details = []
            if realmlist:
                details.append(f"Realmlist: {realmlist}")
            if website:
                details.append(f"Website: {website}")
            if download:
                details.append(f"Download: {download}")
            if support:
                details.append(f"Support: {support}")
            if rates:
                details.append("Rates:\n" + "\n".join(rates))
            if details:
                pieces.append("Server info:\n" + "\n".join(details))
        except Exception:
            pass
        if not pieces:
            return base
        ctx = "\n\n".join(pieces)
        if len(ctx) > RAG_MAX_CHARS:
            ctx = ctx[:RAG_MAX_CHARS]
        guidance = (
            "Use the following knowledge ONLY if it is clearly relevant to the user's question. "
            "Do not list unrelated facts or dump the context. Answer concisely; if unsure, say so."
        )
        return base + "\n\n" + guidance + "\n" + ctx

    def _get_history(self, channel_id: int) -> list[dict]:
        return self._chat_hist.setdefault(channel_id, [])

    def _append_history(self, channel_id: int, role: str, content: str) -> None:
        hist = self._get_history(channel_id)
        hist.append({"role": role, "content": content})
        # Keep last N turns (user+assistant pairs)
        max_msgs = max(0, OLLAMA_HISTORY_TURNS) * 2
        if max_msgs > 0 and len(hist) > max_msgs:
            self._chat_hist[channel_id] = hist[-max_msgs:]
        # Persist
        self._save_history_file()

    def _clear_history(self, channel_id: int) -> None:
        self._chat_hist.pop(channel_id, None)
        self._save_history_file()

    async def on_message(self, message: discord.Message):
        # Only if chatty mode is enabled (env or guild override)
        if not llm_available() or not self._auto_reply_enabled(message.guild.id if message.guild else None):
            return
        # Ignore self/bots
        if message.author.bot:
            return
        # Guild restriction
        if message.guild and not ((ALLOWED_GUILD_ID == 0) or (message.guild.id == ALLOWED_GUILD_ID)):
            return
        # Channel restriction: if ALLOWED_CHANNEL_ID is set, only reply there
        in_allowed_channel = (ALLOWED_CHANNEL_ID == 0) or (message.channel and message.channel.id == ALLOWED_CHANNEL_ID)
        role_allowed = _has_tools_role_member(message.author)
        # If no explicit channel, only reply when mentioned to avoid spam
        mentioned = self.user in getattr(message, "mentions", []) if self.user else False
        if not (in_allowed_channel or role_allowed or mentioned):
            return
        # Need content or image
        content = (message.content or "").strip()
        has_image = any(getattr(a, "content_type", "").startswith("image/") for a in getattr(message, "attachments", []) or [])
        if not content and not has_image:
            return
        lc = content.lower()
        # Quick intent-based answers before LLM
        if in_allowed_channel or mentioned:
            # Help/commands
            if any(k in lc for k in ["commands", "help", "how do i", "what can you do"]):
                try:
                    await message.reply(get_help_overview(), mention_author=False)
                except Exception:
                    pass
                return
            # Register
            if any(k in lc for k in ["register", "create account", "signup", "sign up"]):
                try:
                    await message.reply("To create an account, use `/wowregister` (opens a private modal).", mention_author=False)
                except Exception:
                    pass
                return
            # Reset/change password
            if ("password" in lc) and any(k in lc for k in ["reset", "change", "forgot", "lost"]):
                try:
                    await message.reply("To change or reset your password, use `/wowchangepass` (private modal).", mention_author=False)
                except Exception:
                    pass
                return
            # Realmlist / connect
            if any(k in lc for k in ["realmlist", "connect", "how to connect", "set realmlist"]):
                try:
                    await message.reply(get_connect_instructions(), mention_author=False)
                except Exception:
                    pass
                return
            # Download
            if any(k in lc for k in ["download", "client", "client download"]):
                if DOWNLOAD_URL:
                    try:
                        await message.reply(f"Client download: {DOWNLOAD_URL}", mention_author=False)
                    except Exception:
                        pass
                    return
            # Server status quick reply
            if any(k in lc for k in ["status", "server up", "server down", "online", "uptime"]):
                # Per-user rate limit applies
                try:
                    async with message.channel.typing():
                        try:
                            out = await run_soap(".server info")
                            info = parse_server_info(out)
                        except Exception:
                            info = None
                        await message.reply(format_quick_status(info), mention_author=False)
                except Exception:
                    pass
                return
            # Optional: KB suggestion blurb (disabled by default)
            if KB_SUGGEST_IN_CHAT and len(content) >= 3 and getattr(self, "_rag", None) and self._rag.kb:
                hits = [h for h in (e for e in self._rag.search_kb(content, limit=2))]
                if hits:
                    try:
                        lines = ["You might find these helpful:"]
                        for h in hits:
                            snippet = h.get("text", "").strip().splitlines()[0][:120]
                            lines.append(f"- [{h.get('id')}] {h.get('title')} — {snippet}")
                        await message.reply("\n".join(lines), mention_author=False)
                    except Exception:
                        pass
            # Vision quick reply: describe image
            if has_image and LLM_PROVIDER == "ollama" and OLLAMA_ENABLED and OLLAMA_VISION_ENABLED:
                if not ratelimit(message.author.id, message.channel.id if message.channel else None):
                    return
                try:
                    async with message.channel.typing():
                        img_att = next((a for a in message.attachments if getattr(a, "content_type", "").startswith("image/")), None)
                        if not img_att:
                            return
                        img_bytes = await img_att.read()
                        prompt_text = content if content else "Describe this image."
                        hist = self._get_history(message.channel.id)
                        system = self._get_system_prompt(message.guild.id if message.guild else None)
                        text = await asyncio.to_thread(ollama_chat, prompt_text.strip(), 30.0, system, hist, [img_bytes])
                    if not text:
                        return
                    await send_long_reply(message, text)
                    self._append_history(message.channel.id, "user", prompt_text)
                    self._append_history(message.channel.id, "assistant", text)
                except Exception as e:
                    try:
                        await message.reply(f"🤖 {format_ollama_error(e)}", mention_author=False)
                    except Exception:
                        pass
                return
            # Custom FAQ entries from info file: simple substring match
            try:
                faq = info_get("faq", {}) or {}
                if isinstance(faq, dict):
                    for trigger, reply in faq.items():
                        if isinstance(trigger, str) and isinstance(reply, str) and trigger.lower() in lc:
                            await message.reply(reply, mention_author=False)
                            return
            except Exception:
                pass
        # Simple per-user rate limit
        if not ratelimit(message.author.id, message.channel.id if message.channel else None):
            return  # silent skip to reduce noise
        try:
            async with message.channel.typing():
                # Strip bot mention if present
                if self.user:
                    mention_patterns = [f"<@{self.user.id}>", f"<@!{self.user.id}>"]
                    for m in mention_patterns:
                        content = content.replace(m, "").strip()
                prompt = content
                hist = self._get_history(message.channel.id)
                # Deterministic metric intents (avoid LLM hallucinations)
                low = prompt.lower()
                if METRICS_STRICT:
                    intent = classify_intent(low)
                    if intent:
                        name, slots = intent
                        try:
                            if name == "online_count":
                                n = kpi.kpi_players_online()
                                return await message.reply(
                                    wrap_response("Players online", str(n)), mention_author=False
                                )
                            if name == "total_characters":
                                totals = kpi.kpi_totals()
                                return await message.reply(
                                    wrap_response(
                                        "Characters", str(totals.get("total_chars", 0))
                                    ),
                                    mention_author=False,
                                )
                            if name == "total_accounts":
                                totals = kpi.kpi_totals()
                                return await message.reply(
                                    wrap_response(
                                        "Accounts", str(totals.get("total_accounts", 0))
                                    ),
                                    mention_author=False,
                                )
                            if name == "auction_count":
                                n = kpi.kpi_auction_count()
                                return await message.reply(
                                    wrap_response("Active auctions", str(n)),
                                    mention_author=False,
                                )
                            if name == "server_rates":
                                lines = get_rates_lines()
                                rates = "\n".join(lines) if lines else "No rates configured."
                                return await message.reply(
                                    wrap_response("Server rates", "\n" + rates),
                                    mention_author=False,
                                )
                            if name == "gold_per_hour":
                                return await message.reply("I don’t track gold per hour. Try /wowgold_top or /wowah_hot.", mention_author=False)
                            if name == "bots_count":
                                return await message.reply("Bot count isn’t exposed. Use /wowbots if configured, or ask an admin.", mention_author=False)
                        except Exception:
                            # fall through to LLM
                            pass

                gid = message.guild.id if message.guild else None
                sys_prompt = self._get_system_prompt(gid)
                guard = "Never invent numbers—if a metric is unavailable, say so and suggest a command like /wowkpi."
                if _is_realm_health_query(prompt):
                    facts = kpi.kpi_summary_text()
                    sys_prompt = sys_prompt + "\n\n" + guard + "\nFACTS (live):\n" + facts
                elif self._rag_enabled(gid):
                    sys_prompt = self._build_rag_system(prompt, gid)
                text = await asyncio.to_thread(llm_chat, prompt.strip(), system=sys_prompt, history=hist)
            if not text:
                return
            await send_long_reply(message, text)
            # Update history
            self._append_history(message.channel.id, "user", prompt)
            self._append_history(message.channel.id, "assistant", text)
        except Exception as e:
            # Best-effort friendly error; avoid spamming
            try:
                await message.reply(f"🤖 {format_llm_error(e)}", mention_author=False)
            except Exception:
                pass

bot = Bot()

def channel_allowed(inter: discord.Interaction) -> bool:
    return (ALLOWED_CHANNEL_ID == 0) or (inter.channel and inter.channel.id == ALLOWED_CHANNEL_ID) or _has_tools_role(inter)

def guild_allowed(inter: discord.Interaction) -> bool:
    return (ALLOWED_GUILD_ID == 0) or (inter.guild and inter.guild.id == ALLOWED_GUILD_ID)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    import logging
    import requests as _req

    # Default message
    human = "Something went wrong running this command."

    # Surface underlying HTTP/connection issues if present
    if isinstance(error, app_commands.CommandInvokeError) and getattr(error, 'original', None) is not None:
        orig = error.original
        if isinstance(orig, (_req.Timeout, _req.ConnectionError, _req.HTTPError)):
            human = format_soap_error(orig)
        else:
            human = f"Unexpected error: {orig}"
    elif isinstance(error, app_commands.CheckFailure):
        human = "You cannot use this command here."
    elif hasattr(app_commands, 'CommandOnCooldown') and isinstance(error, app_commands.CommandOnCooldown):
        retry_after = int(getattr(error, 'retry_after', 0))
        human = f"You are on cooldown. Try again in {retry_after}s."

    logging.exception("App command error: %s", error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ {human}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {human}", ephemeral=True)
    except Exception:
        pass

@bot.tree.command(name="registerwow", description="Create a game account privately (opens a modal)")
async def wowregister(interaction: discord.Interaction):
    # Allow anywhere in the guild (modal is private), but still enforce guild restriction
    if not guild_allowed(interaction):
        return
    await interaction.response.send_modal(RegisterModal(user_id=interaction.user.id))

@bot.tree.command(name="wowstatus", description="Show server status (uptime/build/players)")
async def wowstatus(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not enforce_ratelimit_inter(interaction):
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        out = await run_soap(".server info")
        info = parse_server_info(out)

        embed = discord.Embed(title="AzerothCore Server Status", color=0x2ECC71)
        if v := info.get("version"):
            embed.add_field(name="Version", value=v, inline=False)
        if u := info.get("uptime"):
            embed.add_field(name="Uptime", value=u, inline=True)
        if c := info.get("connected"):
            embed.add_field(name="Connected", value=str(c), inline=True)
        if w := info.get("characters"):
            embed.add_field(name="Characters", value=str(w), inline=True)
        if p := info.get("peak"):
            embed.add_field(name="Peak", value=str(p), inline=True)
        # Update time metrics if present
        upd = []
        if m := info.get("update_mean"):
            upd.append(f"mean {m}ms")
        if p95 := info.get("update_p95"):
            upd.append(f"p95 {p95}ms")
        if p99 := info.get("update_p99"):
            upd.append(f"p99 {p99}ms")
        if mx := info.get("update_max"):
            upd.append(f"max {mx}ms")
        if upd:
            embed.add_field(name="Update Diffs", value=", ".join(upd), inline=False)

        # Raw preview fallback if parsing missed important info
        if not info:
            lines = [ln for ln in out.splitlines() if ln.strip()]
            preview = "\n".join(lines[:12]) or "(no output)"
            embed.description = f"```\n{preview[:1000]}\n```"

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_soap_error(e)}", ephemeral=True)

@bot.tree.command(name="wowhelp", description="Show helpful info: commands, connect, links")
@app_commands.describe(topic="Optional topic: commands, connect, resetpw")
async def wowhelp(interaction: discord.Interaction, topic: Optional[str] = None):
    if not require_allowed(interaction):
        return
    topic = (topic or "").lower().strip()
    if topic in ("connect", "realmlist"):
        return await interaction.response.send_message(get_connect_instructions(), ephemeral=True)
    if topic in ("resetpw", "password", "changepw"):
        return await interaction.response.send_message("Use `/wowchangepass` to change/reset your password (private modal).", ephemeral=True)
    # Default overview
    await interaction.response.send_message(get_help_overview(), ephemeral=True)

@bot.tree.command(name="health", description="Bot health ping")
async def health(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    await interaction.response.send_message("ok", ephemeral=True)

@bot.tree.command(name="wowrates", description="Show server rates context")
async def wowrates(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    lines = get_rates_lines()
    if not lines:
        return await interaction.response.send_message("No rates configured.", ephemeral=True)
    await interaction.response.send_message(
        wrap_response("Server rates", "\n" + "\n".join(lines)), ephemeral=True
    )

@bot.tree.command(name="wowbots", description="Show bot status via SOAP (if configured)")
async def wowbots(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    text = await get_bots_status()
    await interaction.followup.send(text, ephemeral=True)

# (wowmetrics command removed per configuration)

@bot.tree.command(name="wowreloadinfo", description="Reload server info from file")
async def wowreloadinfo(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    # Require Manage Server permission
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to reload info.", ephemeral=True)
    try:
        bot._load_info_file()
        keys = ", ".join(sorted(bot._info.keys())) if isinstance(bot._info, dict) else ""
        msg = f"✅ Reloaded info from `{SERVER_INFO_FILE}`" + (f" (keys: {keys})" if keys else "")
        await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to reload: {e}", ephemeral=True)

@bot.tree.command(name="wowdownload", description="Get the client download link")
async def wowdownload(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if DOWNLOAD_URL:
        await interaction.response.send_message(f"Client download: {DOWNLOAD_URL}", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Download link is not configured. Ask an admin to set DOWNLOAD_URL in .env.", ephemeral=True)

@bot.tree.command(name="wowkb", description="Search the WoW 3.3.5a knowledge base")
@app_commands.describe(query="What are you looking for?")
async def wowkb(interaction: discord.Interaction, query: str):
    if not require_allowed(interaction):
        return
    if not getattr(bot, "_rag", None) or not bot._rag.kb:
        return await interaction.response.send_message("⚠️ Knowledge base is empty or not loaded.", ephemeral=True)
    hits = bot._rag.search_kb(query, limit=3)
    if not hits:
        return await interaction.response.send_message("No entries found.", ephemeral=True)
    lines = ["Top results:"]
    for h in hits:
        snippet = h.get("text", "").strip().splitlines()[0][:160]
        lines.append(f"- [{h.get('id')}] {h.get('title')} — {snippet}")
    lines.append("Use `/wowkb_show id:<id>` to view full entry.")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.tree.command(name="wowdocs", description="Search curated documents for answers")
@app_commands.describe(query="What are you looking for?")
async def wowdocs(interaction: discord.Interaction, query: str):
    if not require_allowed(interaction):
        return
    if not getattr(bot, "_rag", None) or not bot._rag.docs:
        return await interaction.response.send_message("⚠️ No curated documents loaded.", ephemeral=True)
    hits = bot._rag.search_docs(query, limit=3)
    if not hits:
        return await interaction.response.send_message("No documents found.", ephemeral=True)
    lines = ["Top document passages:"]
    for h in hits:
        snippet = h.get("text", "").strip().splitlines()[0][:160]
        lines.append(f"- [{h.get('id')}] {h.get('title')} — {snippet}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.tree.command(name="wowdocs_show", description="Show a curated document passage by id")
@app_commands.describe(id="Entry id shown in /wowdocs results")
async def wowdocs_show(interaction: discord.Interaction, id: str):
    if not require_allowed(interaction):
        return
    entry = None
    for e in bot._rag.docs:
        if str(e.get("id")) == id:
            entry = e
            break
    if not entry:
        return await interaction.response.send_message("Entry not found.", ephemeral=True)
    title = entry.get("title")
    text = entry.get("text", "")
    header = f"{title} — {entry.get('id')}"
    if len(text) <= 1800:
        await interaction.response.send_message(f"{header}\n```\n{text}\n```", ephemeral=True)
    else:
        await interaction.response.send_message(header, ephemeral=True)
        chunks = chunk_text(text, 1900)
        for c in chunks:
            await interaction.followup.send(f"```\n{c}\n```", ephemeral=True)

@bot.tree.command(name="wowdocs_reload", description="Reload curated documents from the docs directory")
async def wowdocs_reload(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to reload docs.", ephemeral=True)
    try:
        bot._rag.load_docs()
        await interaction.response.send_message(f"✅ Reloaded docs from `{DOCS_DIR}` with {len(bot._rag.docs)} passages.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to reload docs: {e}", ephemeral=True)

@bot.tree.command(name="wowkb_show", description="Show a knowledge base entry by id")
@app_commands.describe(id="Entry id, e.g., realmlist or addons")
async def wowkb_show(interaction: discord.Interaction, id: str):
    if not require_allowed(interaction):
        return
    entry = None
    for e in bot._rag.kb:
        if str(e.get("id")).lower() == id.lower().strip():
            entry = e
            break
    if not entry:
        return await interaction.response.send_message("Entry not found.", ephemeral=True)
    title = entry.get("title")
    text = entry.get("text", "")
    header = f"[{entry.get('id')}] {title}"
    if len(text) <= 1800:
        await interaction.response.send_message(f"{header}\n```\n{text}\n```", ephemeral=True)
    else:
        # Send header first, then chunked code blocks
        await interaction.response.send_message(header, ephemeral=True)
        chunks = chunk_text(text, 1900)
        for c in chunks:
            await interaction.followup.send(f"```\n{c}\n```", ephemeral=True)

@bot.tree.command(name="wowkbreload", description="Reload the knowledge base from file")
async def wowkbreload(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to reload the KB.", ephemeral=True)
    try:
        bot._rag.load_kb()
        await interaction.response.send_message(f"✅ Reloaded KB from `{KB_FILE}` with {len(bot._rag.kb)} entries.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to reload KB: {e}", ephemeral=True)

@bot.tree.command(name="wowkb_reload", description="Reload the knowledge base (JSON or YAML) from file")
async def wowkb_reload(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to reload the KB.", ephemeral=True)
    try:
        bot._rag.load_kb()
        await interaction.response.send_message(f"✅ Reloaded KB from `{KB_FILE}` with {len(bot._rag.kb)} entries.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to reload KB: {e}", ephemeral=True)

class ChangePasswordModal(Modal, title="Change Game Password"):
    username: TextInput = TextInput(label="Username", placeholder="Your account name", min_length=3, max_length=16)
    new_password: TextInput = TextInput(label="New Password", style=discord.TextStyle.paragraph, placeholder="6–32 chars", min_length=6, max_length=32)

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        cid = interaction.channel.id if interaction.channel else None
        if not ratelimit(self._user_id, cid):
            wait = seconds_until_allowed(self._user_id, cid)
            return await interaction.response.send_message(f"⏳ Please wait {wait}s before trying again.", ephemeral=True)

        u = str(self.username.value).strip()
        p = str(self.new_password.value).strip()
        if not valid_username(u):
            return await interaction.response.send_message("❌ Username must be 3–16 chars (A–Z, a–z, 0–9, _ , -).", ephemeral=True)
        if not valid_password(p):
            return await interaction.response.send_message("❌ Password must be 6–32 chars.", ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # AzerothCore expects the password twice for confirmation
            out = await run_soap(f".account set password {u} {p} {p}")
            ok = ("changed" in out.lower()) or ("success" in out.lower())
            msg = f"{'✅' if ok else '⚠️'} Result for `{u}`:\n```\n{out[:1800]}\n```"
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {format_soap_error(e)}", ephemeral=True)

@bot.tree.command(name="wowchangepass", description="Change a game account password (opens a modal)")
async def wowchangepass(interaction: discord.Interaction):
    if not guild_allowed(interaction):
        return
    await interaction.response.send_modal(ChangePasswordModal(user_id=interaction.user.id))

## /wowonline moved to commands/kpi.py (DB-first with SOAP fallback)

@bot.tree.command(name="wowstats", description="Show DB stats: accounts, characters, guilds (if DB enabled)")
async def wowstats(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    cfg = _db_cfg()
    if not cfg:
        return await interaction.response.send_message("DB is not configured. Set DB_ENABLED=true and credentials.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        accounts, characters, guilds = await asyncio.to_thread(db_get_totals, cfg)
        await interaction.followup.send(
            f"Accounts: {accounts or 0}\nCharacters: {characters or 0}\nGuilds: {guilds or 0}",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(f"❌ DB error: {e}", ephemeral=True)

@bot.tree.command(name="wowask", description="Ask the configured AI model a question")
@app_commands.describe(prompt="Your question or prompt for the model")
async def wowask(interaction: discord.Interaction, prompt: str):
    if not require_allowed(interaction):
        return
    if not prompt or not prompt.strip():
        return await interaction.response.send_message("❌ Please provide a prompt.", ephemeral=True)
    if not enforce_ratelimit_inter(interaction):
        return

    user_prompt = prompt.strip()
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        # Deterministic metric intents
        low = user_prompt.lower()
        if METRICS_STRICT:
            intent = classify_intent(low)
            if intent:
                name, slots = intent
                if name == "online_count":
                    n = kpi.kpi_players_online()
                    return await interaction.followup.send(
                        wrap_response("Players online", str(n)), ephemeral=True
                    )
                if name == "total_characters":
                    totals = kpi.kpi_totals()
                    return await interaction.followup.send(
                        wrap_response("Characters", str(totals.get("total_chars", 0))),
                        ephemeral=True,
                    )
                if name == "total_accounts":
                    totals = kpi.kpi_totals()
                    return await interaction.followup.send(
                        wrap_response("Accounts", str(totals.get("total_accounts", 0))),
                        ephemeral=True,
                    )
                if name == "auction_count":
                    n = kpi.kpi_auction_count()
                    return await interaction.followup.send(
                        wrap_response("Active auctions", str(n)), ephemeral=True
                    )
                if name == "server_rates":
                    lines = get_rates_lines()
                    rates = "\n".join(lines) if lines else "No rates configured."
                    return await interaction.followup.send(
                        wrap_response("Server rates", "\n" + rates), ephemeral=True
                    )
                if name == "gold_per_hour":
                    return await interaction.followup.send("I don’t track gold per hour. Try /wowgold_top or /wowah_hot.", ephemeral=True)
                if name == "bots_count":
                    return await interaction.followup.send("Bot count isn’t exposed. Use /wowbots if configured, or ask an admin.", ephemeral=True)

        # Time queries via tool
        if _is_time_query(prompt):
            t = get_current_time()
            if t.get("ok"):
                return await interaction.followup.send(
                    f"🕒 Current time: {t['iso_local']} ({t['tz_local']})",
                    ephemeral=True,
                )
            return await interaction.followup.send("⚠️ Could not determine current time.", ephemeral=True)

        # Facts injection for realm-health queries
        if _is_realm_health_query(user_prompt):
            facts = kpi.kpi_summary_text()
            guard = "Never invent numbers—if a metric is unavailable, say so and suggest a command like /wowkpi."
            system = (
                bot._get_system_prompt(interaction.guild.id if interaction.guild else None)
                + "\n\n" + guard + "\nFACTS (live):\n" + facts
            )
        else:
            system = bot._build_rag_system(user_prompt, interaction.guild.id if interaction.guild else None)
        guard_text = "If the needed data or docs are missing, reply with 'not sure.'\n"
        text = await asyncio.to_thread(
            llm_chat,
            guard_text + user_prompt,
            system=system,
            history=None,
        )
        if not text:
            return await interaction.followup.send("⚠️ No response from model.", ephemeral=True)
        await send_long_ephemeral(interaction, text)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_llm_error(e)}", ephemeral=True)

@bot.tree.command(name="wowimage", description="Generate an image with the configured AI provider")
@app_commands.describe(prompt="Describe the image", negative="Optional negatives", width="px", height="px")
async def wowimage(interaction: discord.Interaction, prompt: str, negative: Optional[str] = None, width: int = 1024, height: int = 1024):
    if not require_allowed(interaction):
        return
    if not prompt or not prompt.strip():
        return await interaction.response.send_message("❌ Please provide a prompt.", ephemeral=True)
    if not enforce_ratelimit_inter(interaction):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        if LLM_PROVIDER == "arliai" and arliai_client:
            data = arliai_client.txt2img(LLM_IMAGE_MODEL or ARLIAI_IMAGE_MODEL, prompt.strip(), negative_prompt=(negative or ""), width=width, height=height)
            imgs = data.get("images") or []
            if not imgs:
                return await interaction.followup.send("⚠️ No image returned.", ephemeral=True)
            b = base64.b64decode(imgs[0])
            file = discord.File(io.BytesIO(b), filename="ai_image.png")
            await interaction.followup.send(content="Here you go:", file=file, ephemeral=True)
        else:
            await interaction.followup.send("🤖 The current provider does not support text-to-image.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_llm_error(e)}", ephemeral=True)

@bot.tree.command(name="wowupscale", description="Upscale an image with the configured AI provider")
@app_commands.describe(image="Image to upscale", factor="Upscale factor (2-4)")
async def wowupscale(interaction: discord.Interaction, image: discord.Attachment, factor: int = 2):
    if not require_allowed(interaction):
        return
    if factor < 2:
        factor = 2
    if factor > 4:
        factor = 4
    if not enforce_ratelimit_inter(interaction):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        if LLM_PROVIDER == "arliai" and arliai_client:
            raw = await image.read()
            b64 = base64.b64encode(raw).decode("ascii")
            data = arliai_client.upscale(b64, upscaling_resize=factor)
            out = data.get("image")
            if not out:
                return await interaction.followup.send("⚠️ No image returned.", ephemeral=True)
            b = base64.b64decode(out)
            file = discord.File(io.BytesIO(b), filename="ai_upscaled.png")
            await interaction.followup.send(content=f"Upscaled x{factor}:", file=file, ephemeral=True)
        else:
            await interaction.followup.send("🤖 The current provider does not support upscaling.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_llm_error(e)}", ephemeral=True)

@bot.tree.command(name="wowllminfo", description="Show configured LLM provider/model and token limits")
async def wowllminfo(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    parts = [
        f"Provider: {LLM_PROVIDER}",
        f"Text model: {LLM_TEXT_MODEL or (ARLIAI_TEXT_MODEL if LLM_PROVIDER=='arliai' else OLLAMA_MODEL)}",
    ]
    ctx = LLM_CONTEXT_TOKENS if LLM_CONTEXT_TOKENS > 0 else None
    max_out = LLM_MAX_TOKENS
    if LLM_PROVIDER == 'ollama':
        parts.append(f"Host: {OLLAMA_HOST}")
        parts.append(f"Max output tokens (configured): {max_out}")
        if ctx:
            parts.append(f"Context tokens (hint): {ctx}")
    elif LLM_PROVIDER == 'arliai':
        parts.append(f"Host: {ARLIAI_BASE_URL}")
        parts.append(f"Max output tokens (configured): {max_out}")
        if ctx:
            parts.append(f"Context tokens (hint): {ctx}")
        # Best-effort fetch of model info
        try:
            if arliai_client:
                info = arliai_client.model_info(LLM_TEXT_MODEL or ARLIAI_TEXT_MODEL)
                if info:
                    parts.append("Model info (from API):")
                    # Common keys people care about
                    for k in ("id", "context_length", "max_tokens", "max_context_tokens", "owner", "created"):
                        if k in info:
                            parts.append(f"- {k}: {info[k]}")
        except Exception:
            pass
    await interaction.response.send_message("\n".join(parts), ephemeral=True)

@bot.tree.command(name="wowaskimg", description="Ask about an image using Ollama (if enabled)")
@app_commands.describe(image="Image attachment", prompt="Optional question about the image")
async def wowaskimg(interaction: discord.Interaction, image: discord.Attachment, prompt: Optional[str] = None):
    if not guild_allowed(interaction):
        return
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel or with the required role.", ephemeral=True)
    # Only supported with Ollama vision
    if LLM_PROVIDER != "ollama":
        return await interaction.response.send_message("🤖 The current provider does not support image understanding.", ephemeral=True)
    if not OLLAMA_ENABLED or not OLLAMA_VISION_ENABLED:
        return await interaction.response.send_message("🤖 Vision is not enabled. Set OLLAMA_ENABLED=true and OLLAMA_VISION_ENABLED=true.", ephemeral=True)
    if not image or not (getattr(image, "content_type", "").startswith("image/") or str(image.filename).lower().endswith((".png",".jpg",".jpeg",".webp",".bmp",".gif"))):
        return await interaction.response.send_message("❌ Please attach an image.", ephemeral=True)
    cid = interaction.channel.id if interaction.channel else None
    if not ratelimit(interaction.user.id, cid):
        wait = seconds_until_allowed(interaction.user.id, cid)
        return await interaction.response.send_message(f"⏳ Please wait {wait}s.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        img_bytes = await image.read()
        question = (prompt or "Describe this image.").strip()
        system = bot._get_system_prompt(interaction.guild.id if interaction.guild else None)
        text = await asyncio.to_thread(ollama_chat, question, 30.0, system, None, [img_bytes])
        if not text:
            return await interaction.followup.send("⚠️ No response from model.", ephemeral=True)
        await send_long_ephemeral(interaction, text)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_ollama_error(e)}", ephemeral=True)

@bot.tree.command(name="wowascii", description="Generate ASCII art with the configured AI model")
@app_commands.describe(subject="Describe what to draw (ASCII)", width="Max characters per line (hint to the model)")
async def wowascii(interaction: discord.Interaction, subject: str, width: Optional[int] = 60):
    if not require_allowed(interaction):
        return
    if not subject or not subject.strip():
        return await interaction.response.send_message("❌ Please describe what to draw.", ephemeral=True)
    if not enforce_ratelimit_inter(interaction):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        # Nudge the model to output only ASCII inside a code block friendly width
        w = max(20, min(200, int(width or 60)))
        sys_prompt = (
            "You output ONLY ASCII art using standard keyboard characters. "
            "Do not include explanations, headers, or backticks. Keep lines <= " + str(w) + " chars."
        )
        text = await asyncio.to_thread(llm_chat, f"ASCII art of: {subject.strip()}", system=sys_prompt, history=None)
        if not text:
            return await interaction.followup.send("⚠️ No output.", ephemeral=True)
        # Wrap in a code block for monospace display
        await send_long_ephemeral(interaction, text, code_block=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_llm_error(e)}", ephemeral=True)


@bot.tree.command(name="wowpersona_set", description="Set the Ollama system prompt for this server (non-persistent)")
@app_commands.describe(prompt="Describe how the bot should behave in this server")
async def wowpersona_set(interaction: discord.Interaction, prompt: str):
    if not guild_allowed(interaction):
        return
    if not OLLAMA_ENABLED:
        return await interaction.response.send_message("🤖 Ollama is not enabled.", ephemeral=True)
    if not prompt or not prompt.strip():
        return await interaction.response.send_message("❌ Please provide a non-empty prompt.", ephemeral=True)
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
    bot._system_prompt_override[interaction.guild.id] = prompt.strip()
    # Persist persona change
    try:
        bot._save_history_file()
    except Exception:
        pass
    await interaction.response.send_message("✅ Persona updated for this server (resets on restart).", ephemeral=True)

@bot.tree.command(name="wowpersona_show", description="Show the current Ollama system prompt for this server")
async def wowpersona_show(interaction: discord.Interaction):
    if not guild_allowed(interaction):
        return
    if not OLLAMA_ENABLED:
        return await interaction.response.send_message("🤖 Ollama is not enabled.", ephemeral=True)
    prompt = bot._get_system_prompt(interaction.guild.id if interaction.guild else None)
    maxlen = 1800
    if len(prompt) > maxlen:
        prompt = prompt[:maxlen] + "…"
    await interaction.response.send_message(f"Current persona:\n```\n{prompt}\n```", ephemeral=True)

@bot.tree.command(name="wowclearhistory", description="Clear the conversation history for this channel")
async def wowclearhistory(interaction: discord.Interaction):
    if not guild_allowed(interaction):
        return
    if not OLLAMA_ENABLED:
        return await interaction.response.send_message("🤖 Ollama is not enabled.", ephemeral=True)
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel or with the required role.", ephemeral=True)
    if not interaction.channel:
        return await interaction.response.send_message("❌ No channel context.", ephemeral=True)
    bot._clear_history(interaction.channel.id)
    await interaction.response.send_message("✅ Cleared conversation history for this channel.", ephemeral=True)

@bot.tree.command(name="wowrag_on", description="Enable RAG context in auto-replies for this server")
async def wowrag_on(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to change this setting.", ephemeral=True)
    if not interaction.guild:
        return await interaction.response.send_message("❌ Must be used in a server.", ephemeral=True)
    bot._rag_override[interaction.guild.id] = True
    try:
        bot._save_history_file()
    except Exception:
        pass
    await interaction.response.send_message("✅ RAG enabled for auto-replies in this server.", ephemeral=True)

@bot.tree.command(name="wowrag_off", description="Disable RAG context in auto-replies for this server")
async def wowrag_off(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to change this setting.", ephemeral=True)
    if not interaction.guild:
        return await interaction.response.send_message("❌ Must be used in a server.", ephemeral=True)
    bot._rag_override[interaction.guild.id] = False
    try:
        bot._save_history_file()
    except Exception:
        pass
    await interaction.response.send_message("✅ RAG disabled for auto-replies in this server.", ephemeral=True)

@bot.tree.command(name="wowrag_show", description="Show whether RAG is used in auto-replies for this server")
async def wowrag_show(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    gid = interaction.guild.id if interaction.guild else None
    enabled = bot._rag_enabled(gid)
    src = "override" if (gid and gid in bot._rag_override) else "default"
    await interaction.response.send_message(f"RAG in auto-replies: {'ON' if enabled else 'OFF'} ({src})", ephemeral=True)

@bot.tree.command(name="wowautoreply_on", description="Enable auto-replies in this server")
async def wowautoreply_on(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to change this setting.", ephemeral=True)
    if not interaction.guild:
        return await interaction.response.send_message("❌ Must be used in a server.", ephemeral=True)
    bot._auto_reply_override[interaction.guild.id] = True
    try:
        bot._save_history_file()
    except Exception:
        pass
    await interaction.response.send_message("✅ Auto-replies enabled for this server.", ephemeral=True)

@bot.tree.command(name="wowautoreply_off", description="Disable auto-replies in this server")
async def wowautoreply_off(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    if not (interaction.user and getattr(interaction.user, 'guild_permissions', None) and interaction.user.guild_permissions.manage_guild):
        return await interaction.response.send_message("❌ You need Manage Server permission to change this setting.", ephemeral=True)
    if not interaction.guild:
        return await interaction.response.send_message("❌ Must be used in a server.", ephemeral=True)
    bot._auto_reply_override[interaction.guild.id] = False
    try:
        bot._save_history_file()
    except Exception:
        pass
    await interaction.response.send_message("✅ Auto-replies disabled for this server.", ephemeral=True)

@bot.tree.command(name="wowautoreply_show", description="Show whether auto-replies are enabled for this server")
async def wowautoreply_show(interaction: discord.Interaction):
    if not require_allowed(interaction):
        return
    gid = interaction.guild.id if interaction.guild else None
    enabled = bot._auto_reply_enabled(gid)
    src = "override" if (gid and gid in bot._auto_reply_override) else "default"
    await interaction.response.send_message(f"Auto-replies: {'ON' if enabled else 'OFF'} ({src})", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | guilds={len(bot.guilds)}")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN")
    bot.run(TOKEN)
