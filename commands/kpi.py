import os, re, time, json, logging
import discord
from discord import app_commands
import ac_metrics as kpi
from soap import SoapClient


async def _send_defer(itx: discord.Interaction):
    if not itx.response.is_done():
        await itx.response.defer(thinking=True, ephemeral=True)


log = logging.getLogger("acbot.kpi")


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
        text = kpi.kpi_summary_text()
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
        rows = kpi.kpi_top_gold(limit=limit)
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
        rows = kpi.kpi_level_distribution()
        out = " | ".join([f"{r['level']}:{r['n']}" for r in rows]) if rows else "No data."
        await itx.followup.send(f"📊 Levels → {out}", ephemeral=True)
        _log_cmd("wowlevels", t0, rows=len(rows))

    @app_commands.command(name="wowguilds", description="Most active guilds (last N days)")
    @app_commands.describe(days="Days window (default 14)", limit="Max rows (default 10)")
    async def wowguilds(itx: discord.Interaction, days: int = 14, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        rows = kpi.kpi_guild_activity(days=days, limit=limit)
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
        rows = kpi.kpi_auction_hot_items(limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out_lines = []
        for r in rows:
            name = r.get("name") or f"Template {r['item_template']}"
            delta = r.get("delta_24h")
            delta_s = f" (Δ24h {delta:+d})" if delta is not None else ""
            out_lines.append(
                f"{name}: {int(r['listings'])} listings{delta_s}, {int(r['sellers'])} sellers, "
                f"total {kpi.copper_to_gold_s(r['total_buyout'])} / {kpi.copper_to_gold_s(r['total_bid'])}, "
                f"avg {kpi.copper_to_gold_s(r['avg_buyout'])}"
            )
        await itx.followup.send("\n".join(out_lines), ephemeral=True)
        _log_cmd("wowah_hot", t0, rows=len(rows), limit=limit)

    @app_commands.command(name="wowarena", description="Arena rating distribution (top buckets)")
    @app_commands.describe(top="How many rows (default 20)")
    async def wowarena(itx: discord.Interaction, top: int = 20):
        t0 = time.time()
        await _send_defer(itx)
        rows = kpi.kpi_arena_rating_distribution(limit_rows=top)
        out = " | ".join([f"{r['rating']}:{r['teams']}" for r in rows]) if rows else "No data."
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowarena", t0, rows=len(rows), top=top)

    @app_commands.command(name="wowprof", description="Profession counts ≥ threshold (skill_id, min_value)")
    @app_commands.describe(skill_id="Profession skill id (e.g., Enchanting=333)", min_value="Min value (default 300)")
    async def wowprof(itx: discord.Interaction, skill_id: int, min_value: int = 300):
        t0 = time.time()
        await _send_defer(itx)
        n = kpi.kpi_profession_counts(skill_id=skill_id, min_value=min_value)
        await itx.followup.send(f"🛠️ Skill {skill_id} ≥ {min_value}: **{n}** characters", ephemeral=True)
        _log_cmd("wowprof", t0, rows=1, skill_id=skill_id, min_value=min_value)

    # Register all
    tree.add_command(wowkpi_cmd)
    tree.add_command(wowgold_top)
    tree.add_command(wowlevels)
    tree.add_command(wowguilds)
    tree.add_command(wowah_hot)
    tree.add_command(wowarena)
    tree.add_command(wowprof)

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
