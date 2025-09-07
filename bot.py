# bot_modal.py
import os, re, time, asyncio, base64
import discord
import html 
from discord import app_commands
from discord.ui import Modal, TextInput
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SOAP_HOST = os.getenv("SOAP_HOST", "127.0.0.1")
SOAP_PORT = int(os.getenv("SOAP_PORT", "7878"))
SOAP_USER = os.getenv("SOAP_USER")
SOAP_PASS = os.getenv("SOAP_PASS")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", "0"))
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID", "0"))

RATE_SECONDS = 5
_last_call: dict[int, float] = {}

def ratelimit(user_id: int) -> bool:
    now = time.time()
    if now - _last_call.get(user_id, 0) < RATE_SECONDS:
        return False
    _last_call[user_id] = now
    return True

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

async def run_soap(cmd: str) -> str:
    return await asyncio.to_thread(soap_execute, cmd)

class RegisterModal(Modal, title="Create Game Account"):
    username: TextInput = TextInput(label="Username", placeholder="3–16 chars: A–Z a–z 0–9 _ -", min_length=3, max_length=16)
    password: TextInput = TextInput(label="Password", style=discord.TextStyle.paragraph, placeholder="6–32 chars", min_length=6, max_length=32)

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Rate limit & validate
        if not ratelimit(self._user_id):
            return await interaction.response.send_message("⏳ Please wait a few seconds before trying again.", ephemeral=True)

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
            await interaction.followup.send(f"❌ SOAP error: `{e}`", ephemeral=True)

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


class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()  # slash cmds don't need message_content
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # If you restrict to a single guild, register commands there for instant availability
        if ALLOWED_GUILD_ID:
            guild = discord.Object(id=ALLOWED_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

bot = Bot()

def channel_allowed(inter: discord.Interaction) -> bool:
    return (ALLOWED_CHANNEL_ID == 0) or (inter.channel and inter.channel.id == ALLOWED_CHANNEL_ID)

def guild_allowed(inter: discord.Interaction) -> bool:
    return (ALLOWED_GUILD_ID == 0) or (inter.guild and inter.guild.id == ALLOWED_GUILD_ID)

@bot.tree.command(name="registerwow", description="Create a game account privately (opens a modal)")
async def wowregister(interaction: discord.Interaction):
    # Allow anywhere in the guild (modal is private), but still enforce guild restriction
    if not guild_allowed(interaction):
        return
    await interaction.response.send_modal(RegisterModal(user_id=interaction.user.id))

@bot.tree.command(name="wowstatus", description="Show server status (uptime/build/players)")
async def wowstatus(interaction: discord.Interaction):
    if not guild_allowed(interaction):
        return
    # Enforce channel restriction for status spam control
    if not channel_allowed(interaction):
        return await interaction.response.send_message("🔒 Use this command in the designated channel.", ephemeral=True)

    # Rate limit
    if not ratelimit(interaction.user.id):
        return await interaction.response.send_message("⏳ Please wait a few seconds.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        out = await run_soap(".server info")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        preview = "\n".join(lines[:15]) or "(no output)"
        await interaction.followup.send(f"```\n{preview[:1800]}\n```", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ SOAP error: `{e}`", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | guilds={len(bot.guilds)}")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN")
    bot.run(TOKEN)
