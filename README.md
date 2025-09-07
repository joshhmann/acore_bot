acore-bot (Discord + SOAP)

Simple Discord bot for AzerothCore that uses SOAP to:

- Create accounts via a private modal: `/wowregister`
- Show server status with an embed: `/wowstatus`
- Change account password via a private modal: `/wowchangepass`
- Show online player count: `/wowonline`
- Bot presence shows Online/Offline with player count
- Sends a message when the server goes offline/online
- Optional Ollama chat command: `/wowask` (local LLM via Ollama)
- Optional auto-replies: Respond to chatter in a channel using Ollama
 - Built-in helpful replies: server status, how to connect, register, reset password
 - Vision (optional): Ask about images via `/wowaskimg` or by posting an image (auto-reply)
 - Knowledge base: Search 3.3.5a cheatsheet via `/wowkb` and `/wowkb_show`
  - RAG (optional): Answers use local KB + server info as context
  - Curated docs: Drop `.md`/`.txt` in `docs/`, search via `/wowdocs`

Requirements

- Python 3.10+
- A Discord application/bot token
- AzerothCore worldserver with SOAP enabled and reachable from where this bot runs

Setup

1) Create a Discord Bot and invite it to your guild with the applications.commands scope.
2) Ensure worldserver SOAP is enabled and credentials are configured. Verify with curl:

   curl -v \
     -H "Content-Type: text/xml" \
     -H "Authorization: Basic BASE64_SOAPUSER:SOAPPASS" \
     --data '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body><ns1:executeCommand xmlns:ns1="urn:AC"><command>.server info</command></ns1:executeCommand></SOAP-ENV:Body></SOAP-ENV:Envelope>' \
     http://HOST:7878/

   You should receive an XML response containing the command output.

3) Create a `.env` file (do not commit secrets):

   DISCORD_TOKEN=your_discord_bot_token
   SOAP_HOST=127.0.0.1
   SOAP_PORT=7878
   SOAP_USER=soap_username
   SOAP_PASS=soap_password
   # Optional: restrict the bot to a guild/channel
   ALLOWED_GUILD_ID=0
   ALLOWED_CHANNEL_ID=0
   # Optional: poll interval for status presence/notifications
   STATUS_POLL_SECONDS=30
   # Optional: load public info/FAQs from a file
   SERVER_INFO_FILE=server_info.json
   KB_FILE=kb.json
   # Curated documents directory (markdown/text)
   DOCS_DIR=docs
   # Optional: Retrieval-Augmented Generation (context for better answers)
   RAG_ENABLED=true
   RAG_KB_TOPK=3
   RAG_MAX_CHARS=3000
   RAG_DOCS_TOPK=2
   # Optional: enable Ollama chat
   OLLAMA_ENABLED=true
   OLLAMA_HOST=http://127.0.0.1:11434
   OLLAMA_MODEL=llama3
   # Optional: respond to chatter in a text channel (requires Message Content intent in Discord Dev Portal)
   OLLAMA_AUTO_REPLY=true
   # Optional: default persona and memory
   OLLAMA_SYSTEM_PROMPT=You are WowSlumsBot, a concise, friendly assistant focused on AzerothCore and WoW.
   OLLAMA_HISTORY_TURNS=4
   # Optional: persist chat memory and personas across restarts
   CHAT_HISTORY_FILE=chat_history.json
   # Optional: helpful links for FAQ replies
   REALMLIST_HOST=set realmlist logon.yourserver.com
   WEBSITE_URL=https://yourserver.com
   DOWNLOAD_URL=https://yourserver.com/download
   SUPPORT_URL=https://discord.gg/yourserver
   # Optional: vision support (use a vision-capable model like llava)
   OLLAMA_VISION_ENABLED=true

Ollama

- Install Ollama and run the server: `ollama serve`
- Pull a model, e.g.: `ollama pull llama3`
- Ensure `OLLAMA_ENABLED=true` and the host/model match your setup.
- Use `/wowask prompt: "..."` to chat. Replies are ephemeral to reduce noise.
 - Vision: Use a vision-capable model (e.g., `llava:13b`). Enable `OLLAMA_VISION_ENABLED=true` and then use `/wowaskimg` or post an image in the allowed channel. The bot attaches images to the model request.

Auto-reply to chatter

- Enable `OLLAMA_AUTO_REPLY=true` to make the bot respond to messages.
- If `ALLOWED_CHANNEL_ID` is set, bot replies to all messages in that channel.
- If not set, bot only replies when it is mentioned to avoid spam.
- You must enable the “Message Content Intent” for your bot in the Discord Developer Portal and re-invite if needed.
 - If vision is enabled, posting an image in the allowed channel will make the bot describe it (or answer your caption).

Persona and memory

- Default persona is set with `OLLAMA_SYSTEM_PROMPT`.
- Adjust per-server at runtime: `/wowpersona_set "Speak like a goblin engineer."`
- Show current persona: `/wowpersona_show`
- The bot keeps the last `OLLAMA_HISTORY_TURNS` exchanges per channel to maintain context.
- Memory and per-server persona persist to `CHAT_HISTORY_FILE`.
- Clear history for a channel: `/wowclearhistory`

Install & Run

- Using venv + pip:

  python -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r <(python - <<'PY'\nimport tomllib,sys;d=tomllib.load(open('pyproject.toml','rb'));print('\n'.join(d['project']['dependencies']))\nPY)
  .venv/bin/python bot.py

  On Windows PowerShell, adapt paths: `.venv\\Scripts\\python.exe bot.py`.

Slash Commands

- /wowregister: Opens a private modal to create a game account.
- /wowstatus: Shows an embed with uptime, build, online counts, and update diffs.
- /wowchangepass: Opens a private modal to change a game account password.
- /wowonline: Quick online player count.
- /wowhelp: Helpful info (commands, connect, reset password).
- /wowdownload: Returns the configured client download link.
 - /wowkb: Search the local knowledge base for WoW 3.3.5a tips.
 - /wowkb_show: Show a specific KB entry by id.
 - /wowkb_reload: Reload KB from JSON or YAML.
 - /wowdocs_reload: Reload curated docs from the docs directory.
 - /wowautoreply_on|off|show: Toggle/show auto-replies per server.

Notes

- The bot syncs slash commands to a single guild instantly if `ALLOWED_GUILD_ID` is set; otherwise global commands are synced (may take up to an hour to propagate).
- The bot enforces a simple per-user rate limit to avoid SOAP spam.
- Keep `.env` out of source control; rotate tokens if they were exposed.

Knowledge base

- Populate `kb.json` with entries of the form: { id, title, tags[], text }.
- Search with `/wowkb query:"addons"` or `/wowkb query:"realmlist"`.
- Show full content with `/wowkb_show id:<id>`.
- Hot-reload with `/wowkbreload` (Manage Server required).

RAG (local retrieval)

- When `RAG_ENABLED=true`, the bot augments Ollama with snippets from `kb.json` and `server_info.json`.
- It selects top `RAG_KB_TOPK` entries that match the user’s query and adds them to the system prompt (up to `RAG_MAX_CHARS`).
- This improves accuracy for 3.3.5a questions without needing internet access.

Curated documents

- Put `.md` or `.txt` files into the `docs/` directory. They are loaded at startup and chunked for search.
- PDFs are supported if `PyPDF2` is installed; add it to `pyproject.toml` or install manually.
- YAML docs are supported with `PyYAML`. A simple structure is:

  title: Dalaran Portals
  sections:
    - "Alliance portals are at the Silver Enclave..."
    - "Horde portals are at Sunreaver's Sanctuary..."
- Search: `/wowdocs query:"..."` shows top passages with ids; `/wowdocs_show id:<id>` shows the full passage.
- Reload docs without restart: `/wowdocs_reload` (Manage Server required).
- RAG: Top `RAG_DOCS_TOPK` passages are automatically included as additional context when generating answers.

Import Zygor Lua guides (optional)

- Use `zygor_import.py` to convert Zygor `.lua` guides into markdown files under `docs/zygor`.
- Examples:

  # Chunked markdown files (multiple files per guide)
  python zygor_import.py --src "/path/to/ZygorGuidesViewer" --mode md --out docs/zygor --tag Zygor --chunk 800

  # One file per guide (RagStore will chunk internally)
  python zygor_import.py --src "/path/to/ZygorGuidesViewer" --mode md-single --out docs/zygor --tag Zygor

  # Single KB YAML file (no docs files; point KB_FILE to this)
  python zygor_import.py --src "/path/to/ZygorGuidesViewer" --mode kb --out kb-zygor.yaml --tag Zygor --chunk 800

- After importing, run `/wowdocs_reload` and the bot will index these guides for search and RAG.
- Licensing: Ensure you have rights to use the guides. Do not commit proprietary content to a public repo.

YAML examples

- KB example: `kb-example.yaml` (use via `KB_FILE=kb-example.yaml`).
- Doc example: `docs/example.yaml`.

Web search (optional)

- If you want internet answers (Google/SerpAPI/DuckDuckGo), we can add a `/webask` command that fetches results and summarizes with citations. This requires API keys and enabling outbound HTTP on your host.

Server info file (optional)

- Set `SERVER_INFO_FILE=server_info.json` to load public data and FAQs.
- Example `server_info.json`:

  {
    "realmlist": "set realmlist logon.yourserver.com",
    "website": "https://yourserver.com",
    "download": "https://yourserver.com/download",
    "support": "https://discord.gg/yourserver",
    "faq": {
      "how do i connect": "Follow these steps to connect...",
      "reset password": "Use /wowchangepass to change or reset your game password."
    }
  }

- Reload at runtime with `/wowreloadinfo` (requires Manage Server permission).
- Built-in replies (help/connect/status) prefer values from this file, falling back to env vars.
