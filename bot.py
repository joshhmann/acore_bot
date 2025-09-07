# bot_modal.py
import os, re, time, asyncio, base64
from typing import Optional
from urllib.parse import urlparse
import discord
import html 
from discord import app_commands
from discord.ui import Modal, TextInput
from dotenv import load_dotenv
import requests
from utils import json_load, json_save_atomic, chunk_text, send_ephemeral, send_long_ephemeral, send_long_reply
from soap import SoapClient
from ollama import OllamaClient
from rag_store import RagStore

load_dotenv()

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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_AUTO_REPLY = os.getenv("OLLAMA_AUTO_REPLY", "false").lower() in {"1","true","yes","on"}
OLLAMA_SYSTEM_PROMPT = os.getenv("OLLAMA_SYSTEM_PROMPT", "You are WowSlumsBot, a concise, friendly assistant focused on AzerothCore, World of Warcraft private server operations, and helpful Discord chat. Answer briefly (<= 4 sentences) unless asked for details.")
OLLAMA_HISTORY_TURNS = int(os.getenv("OLLAMA_HISTORY_TURNS", "50"))
OLLAMA_VISION_ENABLED = os.getenv("OLLAMA_VISION_ENABLED", "false").lower() in {"1","true","yes","on"}
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
try:
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
except Exception:
    OLLAMA_TEMPERATURE = 0.7

# Optional: Retrieval-Augmented Generation (use local KB/server info as context)
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in {"1","true","yes","on"}
RAG_KB_TOPK = int(os.getenv("RAG_KB_TOPK", "3"))
RAG_MAX_CHARS = int(os.getenv("RAG_MAX_CHARS", "3000"))
RAG_DOCS_TOPK = int(os.getenv("RAG_DOCS_TOPK", "2"))
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

RATE_SECONDS = 5
_last_call: dict[int, float] = {}

def ratelimit(user_id: int) -> bool:
    now = time.time()
    if now - _last_call.get(user_id, 0) < RATE_SECONDS:
        return False
    _last_call[user_id] = now
    return True

def seconds_until_allowed(user_id: int) -> int:
    now = time.time()
    last = _last_call.get(user_id, 0)
    remaining = int(max(0, RATE_SECONDS - (now - last)))
    return remaining

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

def require_allowed(inter: discord.Interaction) -> bool:
    if not ((ALLOWED_GUILD_ID == 0) or (inter.guild and inter.guild.id == ALLOWED_GUILD_ID)):
        return False
    if not ((ALLOWED_CHANNEL_ID == 0) or (inter.channel and inter.channel.id == ALLOWED_CHANNEL_ID)):
        # Channel restricted; attempt to notify
        try:
            # Note: function may be called before a response is created
            # Use send_ephemeral for safety
            import asyncio as _a
            _a.create_task(send_ephemeral(inter, "🔒 Use this command in the designated channel."))
        except Exception:
            pass
        return False
    return True

def enforce_ratelimit_inter(inter: discord.Interaction) -> bool:
    uid = inter.user.id if inter.user else 0
    if not ratelimit(uid):
        try:
            wait = seconds_until_allowed(uid)
            import asyncio as _a
            _a.create_task(send_ephemeral(inter, f"⏳ Please wait {wait}s."))
        except Exception:
            pass
        return False
    return True

"""Chunking + long send helpers are imported"""

# ---- Ollama helpers ----
ollama_client = OllamaClient(OLLAMA_HOST, OLLAMA_MODEL, num_predict=OLLAMA_NUM_PREDICT, temperature=OLLAMA_TEMPERATURE)

def ollama_available() -> bool:
    return OLLAMA_ENABLED and ollama_client.available

def ollama_chat(prompt: str, timeout: float = 15.0, system: Optional[str] = None, history: Optional[list[dict]] = None, images: Optional[list[bytes]] = None) -> str:
    return ollama_client.chat(prompt, timeout=timeout, system=system, history=history, images=images)

def format_ollama_error(e: Exception) -> str:
    return ollama_client.format_error(e)

class RegisterModal(Modal, title="Create Game Account"):
    username: TextInput = TextInput(label="Username", placeholder="3–16 chars: A–Z a–z 0–9 _ -", min_length=3, max_length=16)
    password: TextInput = TextInput(label="Password", style=discord.TextStyle.paragraph, placeholder="6–32 chars", min_length=6, max_length=32)

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Rate limit & validate
        if not ratelimit(self._user_id):
            wait = seconds_until_allowed(self._user_id)
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

def get_help_overview() -> str:
    lines = [
        "Commands:",
        "- /wowstatus — Show server status (embed)",
        "- /wowregister — Create a game account (private modal)",
        "- /wowchangepass — Change a game password (private modal)",
        "- /wowonline — Show online player count",
    ]
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
        # Knowledge base entries
        self._kb: list[dict] = []
        # Curated documents (chunked)
        self._docs: list[dict] = []
        # History file path
        self._history_file: str = CHAT_HISTORY_FILE
        # Auto-reply override per guild
        self._auto_reply_override: dict[int, bool] = {}

    async def setup_hook(self):
        # If you restrict to a single guild, register commands there for instant availability
        if ALLOWED_GUILD_ID:
            guild = discord.Object(id=ALLOWED_GUILD_ID)
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
                    "auto_reply": {str(k): v for k, v in (self._auto_reply_override or {}).items()}
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
            try:
                out = await run_soap(".server info")
                info = parse_server_info(out)
                online = True
                connected = info.get("connected")
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

    def _build_rag_system(self, query: str, guild_id: Optional[int]) -> str:
        base = self._get_system_prompt(guild_id)
        if not RAG_ENABLED:
            return base
        pieces: list[str] = []
        # KB hits
        try:
            if getattr(self, "_rag", None) and self._rag.kb and query:
                hits = self._rag.search_kb(query, limit=max(1, RAG_KB_TOPK))
                for h in hits:
                    title = h.get("title", "")
                    text = (h.get("text", "") or "").strip()
                    if text:
                        pieces.append(f"KB: {title}\n{text}")
        except Exception:
            pass
        # Curated docs hits
        try:
            if getattr(self, "_rag", None) and self._rag.docs and query and RAG_DOCS_TOPK > 0:
                hits = self._rag.search_docs(query, limit=RAG_DOCS_TOPK)
                for h in hits:
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
            details = []
            if realmlist:
                details.append(f"Realmlist: {realmlist}")
            if website:
                details.append(f"Website: {website}")
            if download:
                details.append(f"Download: {download}")
            if support:
                details.append(f"Support: {support}")
            if details:
                pieces.append("Server info:\n" + "\n".join(details))
        except Exception:
            pass
        if not pieces:
            return base
        ctx = "\n\n".join(pieces)
        if len(ctx) > RAG_MAX_CHARS:
            ctx = ctx[:RAG_MAX_CHARS]
        return base + "\n\n" + "You also have access to the following relevant knowledge. Prefer it over guessing:\n" + ctx

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
        if not OLLAMA_ENABLED or not self._auto_reply_enabled(message.guild.id if message.guild else None):
            return
        # Ignore self/bots
        if message.author.bot:
            return
        # Guild restriction
        if message.guild and not ((ALLOWED_GUILD_ID == 0) or (message.guild.id == ALLOWED_GUILD_ID)):
            return
        # Channel restriction: if ALLOWED_CHANNEL_ID is set, only reply there
        in_allowed_channel = (ALLOWED_CHANNEL_ID == 0) or (message.channel and message.channel.id == ALLOWED_CHANNEL_ID)
        # If no explicit channel, only reply when mentioned to avoid spam
        mentioned = self.user in getattr(message, "mentions", []) if self.user else False
        if not (in_allowed_channel or mentioned):
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
            # KB quick search
            if len(content) >= 3 and getattr(self, "_rag", None) and self._rag.kb:
                hits = self._rag.search_kb(content, limit=3)
                if hits:
                    try:
                        lines = ["Knowledge base matches:"]
                        for h in hits:
                            snippet = h.get("text", "").strip().splitlines()[0][:120]
                            lines.append(f"- [{h.get('id')}] {h.get('title')} — {snippet}")
                        lines.append("Use `/wowkb_show id:<id>` to view full entry.")
                        await message.reply("\n".join(lines), mention_author=False)
                        return
                    except Exception:
                        pass
            # Vision quick reply: describe image
            if has_image and OLLAMA_ENABLED and OLLAMA_VISION_ENABLED:
                if not ratelimit(message.author.id):
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
        if not ratelimit(message.author.id):
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
                system = self._build_rag_system(prompt, message.guild.id if message.guild else None)
                text = await asyncio.to_thread(ollama_chat, prompt.strip(), 20.0, system, hist)
            if not text:
                return
            await send_long_reply(message, text)
            # Update history
            self._append_history(message.channel.id, "user", prompt)
            self._append_history(message.channel.id, "assistant", text)
        except Exception as e:
            # Best-effort friendly error; avoid spamming
            try:
                await message.reply(f"🤖 {format_ollama_error(e)}", mention_author=False)
            except Exception:
                pass

bot = Bot()

def channel_allowed(inter: discord.Interaction) -> bool:
    return (ALLOWED_CHANNEL_ID == 0) or (inter.channel and inter.channel.id == ALLOWED_CHANNEL_ID)

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
        if not ratelimit(self._user_id):
            wait = seconds_until_allowed(self._user_id)
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

@bot.tree.command(name="wowonline", description="Show number of connected players")
async def wowonline(interaction: discord.Interaction):
    if not guild_allowed(interaction):
        return
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel.", ephemeral=True)
    if not ratelimit(interaction.user.id):
        wait = seconds_until_allowed(interaction.user.id)
        return await interaction.response.send_message(f"⏳ Please wait {wait}s.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        out = await run_soap(".server info")
        info = parse_server_info(out)
        connected = info.get("connected")
        if connected is None:
            # Fallback to raw search if parser missed it
            m = re.search(r"Connected players:\s*(\d+)", out, re.I)
            connected = int(m.group(1)) if m else None
        if connected is None:
            await interaction.followup.send("⚠️ Could not determine online players.", ephemeral=True)
        else:
            await interaction.followup.send(f"🟢 Players online: {connected}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_soap_error(e)}", ephemeral=True)

@bot.tree.command(name="wowask", description="Ask Ollama a question (if enabled)")
@app_commands.describe(prompt="Your question or prompt for the model")
async def wowask(interaction: discord.Interaction, prompt: str):
    if not guild_allowed(interaction):
        return
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel.", ephemeral=True)
    if not ollama_available():
        return await interaction.response.send_message("🤖 Ollama is not enabled. Set OLLAMA_ENABLED=true in .env.", ephemeral=True)
    if not prompt or not prompt.strip():
        return await interaction.response.send_message("❌ Please provide a prompt.", ephemeral=True)
    if not ratelimit(interaction.user.id):
        wait = seconds_until_allowed(interaction.user.id)
        return await interaction.response.send_message(f"⏳ Please wait {wait}s.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        # Stateless chat by default, but include system prompt for style
        system = bot._build_rag_system(prompt, interaction.guild.id if interaction.guild else None)
        text = await asyncio.to_thread(ollama_chat, prompt.strip(), 20.0, system, None)
        if not text:
            return await interaction.followup.send("⚠️ No response from model.", ephemeral=True)
        await send_long_ephemeral(interaction, text)
    except Exception as e:
        await interaction.followup.send(f"❌ {format_ollama_error(e)}", ephemeral=True)

@bot.tree.command(name="wowaskimg", description="Ask about an image using Ollama (if enabled)")
@app_commands.describe(image="Image attachment", prompt="Optional question about the image")
async def wowaskimg(interaction: discord.Interaction, image: discord.Attachment, prompt: Optional[str] = None):
    if not guild_allowed(interaction):
        return
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel.", ephemeral=True)
    if not OLLAMA_ENABLED or not OLLAMA_VISION_ENABLED:
        return await interaction.response.send_message("🤖 Vision is not enabled. Set OLLAMA_ENABLED=true and OLLAMA_VISION_ENABLED=true.", ephemeral=True)
    if not image or not (getattr(image, "content_type", "").startswith("image/") or str(image.filename).lower().endswith((".png",".jpg",".jpeg",".webp",".bmp",".gif"))):
        return await interaction.response.send_message("❌ Please attach an image.", ephemeral=True)
    if not ratelimit(interaction.user.id):
        wait = seconds_until_allowed(interaction.user.id)
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
        return await interaction.response.send_message("🔒 Use this command in the designated channel.", ephemeral=True)
    if not interaction.channel:
        return await interaction.response.send_message("❌ No channel context.", ephemeral=True)
    bot._clear_history(interaction.channel.id)
    await interaction.response.send_message("✅ Cleared conversation history for this channel.", ephemeral=True)

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
