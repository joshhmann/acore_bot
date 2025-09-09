import os, re, time, json, logging
import discord
from discord import app_commands
import ac_metrics as kpi
from soap import SoapClient
from named_queries import run_named_query


async def _send_defer(itx: discord.Interaction):
    if not itx.response.is_done():
        await itx.response.defer(thinking=True, ephemeral=True)


log = logging.getLogger("acbot.kpi")

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _log_cmd(name: str, t0: float, rows: int | None = None, **extra):
    payload = {"cmd": name, "ms": int((time.time() - t0) * 1000)}
    if rows is not None:
        payload["rows"] = rows
    payload.update(extra)
    try:
        log.info(json.dumps(payload))
    except Exception:
        pass


def setup_kpi(tree: app_commands.CommandTree):
    # SOAP fallback client if DB is disabled
    soap = SoapClient(
        os.getenv("SOAP_HOST", "127.0.0.1"),
        int(os.getenv("SOAP_PORT", "7878")),
        os.getenv("SOAP_USER", ""),
        os.getenv("SOAP_PASS", ""),
    )

    @app_commands.command(name="wowkpi", description="Realm KPIs (online, totals, arena, top gold)")
    async def wowkpi_cmd(itx: discord.Interaction):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowkpi", t0, rows=0)
            return
        text = await run_named_query("wowkpi")
        if not text:
            await itx.followup.send("No data.", ephemeral=True)
        else:
            await itx.followup.send(text, ephemeral=True)
        _log_cmd("wowkpi", t0)

    @app_commands.command(name="wowonline", description="Players online now")
    async def wowonline_db(itx: discord.Interaction):
        t0 = time.time()
        await _send_defer(itx)
        n = None
        try:
            # Try DB
            n = kpi.kpi_players_online()
        except Exception:
            n = None
        if n is None or n == 0:
            # SOAP fallback
            try:
                out = soap.execute(".server info")
                m = re.search(r"Connected players:\s*(\d+)", out, re.I)
                if m:
                    n = int(m.group(1))
            except Exception:
                n = None
        if n is None:
            await itx.followup.send("⚠️ Could not determine online players.", ephemeral=True)
            return
        await itx.followup.send(f"🟢 Players online: **{n}**", ephemeral=True)
        _log_cmd("wowonline", t0, rows=1)

    @app_commands.command(name="wowgold_top", description="Top characters by gold")
    @app_commands.describe(limit="How many to show (default 10)")
    async def wowgold_top(itx: discord.Interaction, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowgold_top", t0, rows=0, limit=limit)
            return
        rows = await run_named_query("wowgold_top", limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        lines = [
            f"{i+1}. **{r['name']}** (Lv {r['level']}) — {kpi.copper_to_gold_s(r['money'])}"
            for i, r in enumerate(rows)
        ]
        await itx.followup.send("\n".join(lines), ephemeral=True)
        _log_cmd("wowgold_top", t0, rows=len(rows), limit=limit)

    @app_commands.command(name="wowlevels", description="Level distribution")
    async def wowlevels(itx: discord.Interaction):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowlevels", t0, rows=0)
            return
        rows = await run_named_query("wowlevels")
        out = " | ".join([f"{r['level']}:{r['n']}" for r in rows]) if rows else "No data."
        await itx.followup.send(f"📊 Levels → {out}", ephemeral=True)
        _log_cmd("wowlevels", t0, rows=len(rows))

    @app_commands.command(name="wowguilds", description="Most active guilds (last N days)")
    @app_commands.describe(days="Days window (default 14)", limit="Max rows (default 10)")
    async def wowguilds(itx: discord.Interaction, days: int = 14, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowguilds", t0, rows=0, days=days, limit=limit)
            return
        rows = await run_named_query("wowguilds", days=days, limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out = "\n".join([f"{r['guild']}: {r['active_members']}" for r in rows])
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowguilds", t0, rows=len(rows), days=days, limit=limit)

    @app_commands.command(name="wowah_hot", description="Most listed items on AH")
    @app_commands.describe(limit="Max rows (default 10)")
    async def wowah_hot(itx: discord.Interaction, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowah_hot", t0, rows=0, limit=limit)
            return
        rows = await run_named_query("wowah_hot", limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out_lines = []
        for r in rows:
            name = r.get("name") or f"Template {r['item_template']}"
            out_lines.append(
                f"{name}: {int(r['listings'])} listings, avg {kpi.copper_to_gold_s(r['avg_buyout'])}"
            )
        await itx.followup.send("\n".join(out_lines), ephemeral=True)
        _log_cmd("wowah_hot", t0, rows=len(rows), limit=limit)

    @app_commands.command(name="wowarena", description="Arena rating distribution (top buckets)")
    @app_commands.describe(top="How many rows (default 20)")
    async def wowarena(itx: discord.Interaction, top: int = 20):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowarena", t0, rows=0, top=top)
            return
        rows = await run_named_query("wowarena", top=top)
        out = " | ".join([f"{r['rating']}:{r['teams']}" for r in rows]) if rows else "No data."
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowarena", t0, rows=len(rows), top=top)

    @app_commands.command(name="wowprof", description="Profession counts ≥ threshold (skill_id, min_value)")
    @app_commands.describe(skill_id="Profession skill id (e.g., Enchanting=333)", min_value="Min value (default 300)")
    async def wowprof(itx: discord.Interaction, skill_id: int, min_value: int = 300):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowprof", t0, rows=0, skill_id=skill_id, min_value=min_value)
            return
        n = await run_named_query("wowprof", skill_id=skill_id, min_value=min_value)
        await itx.followup.send(
            f"🛠️ Skill {skill_id} ≥ {min_value}: **{n}** characters", ephemeral=True
        )
        _log_cmd("wowprof", t0, rows=1, skill_id=skill_id, min_value=min_value)

    @app_commands.command(name="wowfactions", description="Faction counts ≥ min level")
    @app_commands.describe(min_level="Minimum level filter (default 1)")
    async def wowfactions(itx: discord.Interaction, min_level: int = 1):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowfactions", t0, rows=0, min_level=min_level)
            return
        rows = await run_named_query("wowfactions", min_level=min_level)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out = " | ".join(
            [
                f"{r.get('faction', r.get('name', '?'))}: {r.get('n', r.get('count', r.get('players')))}"
                for r in rows
            ]
        )
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowfactions", t0, rows=len(rows), min_level=min_level)

    @app_commands.command(name="wowraceclass", description="Race/Class counts ≥ min level")
    @app_commands.describe(min_level="Minimum level filter (default 1)", limit="Max rows (default 10)")
    async def wowraceclass(itx: discord.Interaction, min_level: int = 1, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowraceclass", t0, rows=0, min_level=min_level, limit=limit)
            return
        rows = await run_named_query("wowraceclass", min_level=min_level, limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        lines = [
            f"{i+1}. {r.get('race', '?')}/{r.get('class', '?')}: {r.get('n', r.get('count', r.get('players')))}"
            for i, r in enumerate(rows)
        ]
        await itx.followup.send("\n".join(lines), ephemeral=True)
        _log_cmd("wowraceclass", t0, rows=len(rows), min_level=min_level, limit=limit)

    @app_commands.command(name="wowactive_guilds", description="Guilds with active members in last N days")
    @app_commands.describe(days="Days window (default 14)", limit="Max rows (default 10)")
    async def wowactive_guilds(itx: discord.Interaction, days: int = 14, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowactive_guilds", t0, rows=0, days=days, limit=limit)
            return
        rows = await run_named_query("wowactive_guilds", days=days, limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out = "\n".join(
            [f"{r.get('guild', '?')}: {r.get('active_members', r.get('n', r.get('count', 0)))}" for r in rows]
        )
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowactive_guilds", t0, rows=len(rows), days=days, limit=limit)

    # Register all
    tree.add_command(wowkpi_cmd)
    tree.add_command(wowgold_top)
    tree.add_command(wowlevels)
    tree.add_command(wowguilds)
    tree.add_command(wowah_hot)
    tree.add_command(wowarena)
    tree.add_command(wowprof)
    tree.add_command(wowfactions)
    tree.add_command(wowraceclass)
    tree.add_command(wowactive_guilds)

    @app_commands.command(name="wowfind_char", description="Find characters by name (partial match)")
    @app_commands.describe(name="Name or part of name", limit="Max rows (default 10)")
    async def wowfind_char(itx: discord.Interaction, name: str, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        try:
            rows = kpi.kpi_find_characters(name, limit=max(1, min(50, limit)))
        except Exception:
            rows = []
        if not rows:
            await itx.followup.send("No characters found.", ephemeral=True)
            return
        lines = []
        for r in rows:
            online = "🟢" if r.get("online") else "⚫"
            guild = r.get("guild") or "(no guild)"
            lines.append(f"{online} {r['name']} (Lv {r['level']}) — {guild}")
        await itx.followup.send("\n".join(lines), ephemeral=True)
        _log_cmd("wowfind_char", t0, rows=len(rows), query=name, limit=limit)

    tree.add_command(wowfind_char)
