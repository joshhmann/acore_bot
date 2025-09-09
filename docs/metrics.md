ACbot Metrics
==============

Env
---

DB_ENABLED=true
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=acbot_ro
DB_PASS=CHANGE_ME
DB_AUTH_DB=auth
DB_CHAR_DB=characters
DB_WORLD_DB=world
METRICS_TTL_SECONDS=8
INSIGHTS_QPS=5
OLLAMA_TOOLS_ENABLED=true

Commands
--------

- /wowkpi — realm snapshot (online, totals, arena, top gold)
- /wowonline — players online now (prefers DB)
- /wowgold_top [limit]
- /wowlevels — level distribution
- /wowguilds [days=14] [limit=10]
- /wowah_hot [limit=10] — auction hot items (by item_template)
- /wowarena [top=20] — rating:teams pairs
- /wowprof [skill_id] [min_value=300] — profession counts
- /wowfind_char [name] [limit=10] — search characters by name
- /health — bot health ping

Usage examples
--------------

```text
/wowkpi
🟢 Online now: **41**
🧍 Characters: **120**, 👤 Accounts: **40**
🏟️ Arena (top buckets): 2200:5 | 2100:8
💰 Top gold: Alice (Lv 80): 123g 45s 67c
```

```text
/health
✅ ACbot ok (uptime 2h, DB 12ms)
```

Exports
-------

Most commands accept `format:json` or `format:csv` to download data.

```text
/wowkpi format:json
{"online":41,"totals":{"total_chars":120,"total_accounts":40}}
```

Schema notes (AzerothCore defaults)
-----------------------------------

- characters: online, level, money, logout_time
- character_online: presence (preferred)
- guild, guild_member
- auctionhouse: item_template, buyoutprice (copper)
- arena_team: rating
- character_skills: skill, value
- auth.account
- auth.account_banned

Common profession skill IDs
---------------------------

| Profession       | ID  |
|------------------|-----|
| Alchemy          | 171 |
| Herbalism        | 182 |
| Mining           | 186 |
| Blacksmithing    | 164 |
| Leatherworking   | 165 |
| Engineering      | 202 |
| Enchanting       | 333 |
| Tailoring        | 197 |
| Skinning         | 393 |
| Cooking          | 185 |
| First Aid        | 129 |
| Fishing          | 356 |
| Jewelcrafting    | 755 |
| Inscription      | 773 |

Money units
-----------

- Stored in copper. 1g = 100s = 10000c.

