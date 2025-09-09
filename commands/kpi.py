import os, re, time, json, logging, io, csv
import discord
from discord import app_commands
from typing import Literal

import ac_metrics as kpi
from soap import SoapClient
from utils.formatters import copper_to_gsc, rows_to_embed

from named_queries import run_named_query

import slum_queries as sq
from utils.tool_logging import tool_context

# Optional formatter helpers (fallbacks provided if module not present)
try:
    from utils.formatter import format_gold, normalize_item_name, wrap_response
except Exception:
    def format_gold(copper: int) -> str:
        # fallback to existing util if present, else simple formatter
        try:
            return kpi.copper_to_gold_s(copper)
        except Exception:
            g, rem = divmod(int(copper), 10000)
            s, c = divmod(rem, 100)
            return f"{g}g {s}s {c}c"

    def normalize_item_name(name: str) -> str:
        return str(name)

    def wrap_response(title: str, content: str) -> str:
        return f"**{title}**\n{content}"


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


async def _send_serialized(
    itx: discord.Interaction,
    data: object,
    fmt: Literal["json", "csv"],
    name: str,
) -> None:
    if fmt == "json":
        buf = io.BytesIO(
            json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        )
        file = discord.File(buf, filename=f"{name}.json")
    else:
        out = io.StringIO()
        if isinstance(data, list) and data and isinstance(data[0], dict):
            w = csv.DictWriter(out, fieldnames=data[0].keys())
            w.writeheader()
            w.writerows(data)
        elif isinstance(data, dict):
            w = csv.writer(out)
            for k, v in data.items():
                w.writerow([k, json.dumps(v, ensure_ascii=False)])
        else:
            w = csv.writer(out)
            if isinstance(data, list):
                for row in data:
                    w.writerow([row])
            else:
                w.writerow([data])
        buf = io.BytesIO(out.getvalue().encode("utf-8"))
        file = discord.File(buf, filename=f"{name}.csv")
    await itx.followup.send(file=file, ephemeral=True)


def setup_kpi(tree: app_commands.CommandTree):
    # SOAP fallback client if DB is disabled
    soap = SoapClient(
        os.getenv("SOAP_HOST", "127.0.0.1"),
        int(os.getenv("SOAP_PORT", "7878")),
        os.getenv("SOAP_USER", ""),
        os.getenv("SOAP_PASS", ""),
    )

    @app_commands.command(name="wowkpi", description="Realm KPIs (online, totals, arena, top gold)")
    @app_commands.describe(format="Optional export format")
    async def wowkpi_cmd(
        itx: discord.Interaction, format: Literal["json", "csv"] | None = None
    ):
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

        with tool_context(
            "kpi_summary",
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            if format:
                data = json.loads(kpi.kpi_summary_json())
                await _send_serialized(itx, data, format, "wowkpi")
                tlog(rows=1, cache_hit=getattr(kpi, "last_cache_hit", False))
            else:
                text = kpi.kpi_summary_text()
                await itx.followup.send(text, ephemeral=True)
                tlog(rows=1, cache_hit=getattr(kpi, "last_cache_hit", False))
        _log_cmd("wowkpi", t0, rows=1, fmt=format)

    @app_commands.command(name="wowonline", description="Players online now")
    @app_commands.describe(format="Optional export format")
    async def wowonline_db(
        itx: discord.Interaction, format: Literal["json", "csv"] | None = None
    ):
        t0 = time.time()
        await _send_defer(itx)
        n = None
        with tool_context(
            "kpi_players_online",
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            try:
                # Try DB
                n = kpi.kpi_players_online()
                tlog(rows=1, cache_hit=getattr(kpi, "last_cache_hit", False))
            except Exception as e:
                tlog(error=str(e), db_timeout="timeout" in str(e).lower())
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

        if format:
            await _send_serialized(itx, {"online": n}, format, "wowonline")
        else:
            await itx.followup.send(wrap_response("Players online", str(n)), ephemeral=True)
        _log_cmd("wowonline", t0, rows=1, fmt=format)

    @app_commands.command(name="wowgold_top", description="Top characters by gold")
    @app_commands.describe(
        limit="How many to show (default 10)", format="Optional export format"
    )
    async def wowgold_top(
        itx: discord.Interaction,
        limit: int = 10,
        format: Literal["json", "csv"] | None = None,
    ):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowgold_top", t0, rows=0, limit=limit)
            return
        rows = await run_named_query("wowgold_top", limit=limit)

        with tool_context(
            "kpi_top_gold",
            params={"limit": limit},
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            rows = kpi.kpi_top_gold(limit=limit)
            tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)

        lines = [
            f"{i+1}. **{r['name']}** (Lv {r['level']}) — {copper_to_gsc(r['money'])}"
            for i, r in enumerate(rows)
        ]
        await itx.followup.send(embed=rows_to_embed("Top characters by gold", lines), ephemeral=True)
        _log_cmd("wowgold_top", t0, rows=len(rows), limit=limit)
        if format:
            await _send_serialized(itx, rows, format, "wowgold_top")
        else:
            lines = [
                f"{i+1}. **{r['name']}** (Lv {r['level']}) — {format_gold(r['money'])}"
                for i, r in enumerate(rows)
            ]
            await itx.followup.send(wrap_response("Top gold", "\n".join(lines)), ephemeral=True)
        _log_cmd("wowgold_top", t0, rows=len(rows), limit=limit, fmt=format)
    @app_commands.command(name="wowlevels", description="Level distribution")
    @app_commands.describe(format="Optional export format")
    async def wowlevels(
        itx: discord.Interaction, format: Literal["json", "csv"] | None = None
    ):
        t0 = time.time()
        await _send_defer(itx)
        rows = kpi.kpi_level_distribution()
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        lines = [f"{r['level']}: {r['n']}" for r in rows]
        await itx.followup.send(embed=rows_to_embed("Level distribution", lines), ephemeral=True)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowlevels", t0, rows=0)
            return
        rows = await run_named_query("wowlevels")
        out = " | ".join([f"{r['level']}:{r['n']}" for r in rows]) if rows else "No data."
        await itx.followup.send(f"📊 Levels → {out}", ephemeral=True)
        _log_cmd("wowlevels", t0, rows=len(rows))

        with tool_context(
            "kpi_level_distribution",
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            rows = kpi.kpi_level_distribution()
            tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))

        if format:
            await _send_serialized(itx, rows, format, "wowlevels")
        else:
            out = " | ".join([f"{r['level']}:{r['n']}" for r in rows]) if rows else "No data."
            await itx.followup.send(wrap_response("Level distribution", out), ephemeral=True)
        _log_cmd("wowlevels", t0, rows=len(rows), fmt=format)

    @app_commands.command(name="wowguilds", description="Most active guilds (last N days)")
    @app_commands.describe(
        days="Days window (default 14)",
        limit="Max rows (default 10)",
        format="Optional export format",
    )
    async def wowguilds(
        itx: discord.Interaction,
        days: int = 14,
        limit: int = 10,
        format: Literal["json", "csv"] | None = None,
    ):
        t0 = time.time()
        await _send_defer(itx)

        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowguilds", t0, rows=0, days=days, limit=limit)
            return
        rows = await run_named_query("wowguilds", days=days, limit=limit)

        with tool_context(
            "kpi_guild_activity",
            params={"days": days, "limit": limit},
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            rows = kpi.kpi_guild_activity(days=days, limit=limit)
            tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        lines = [f"{r['guild']}: {r['active_members']}" for r in rows]
        await itx.followup.send(
            embed=rows_to_embed("Most active guilds", lines), ephemeral=True
        )
        _log_cmd("wowguilds", t0, rows=len(rows), days=days, limit=limit)

    @app_commands.command(name="wowactive_guilds", description="Guild activity over N days (cached delta)")
    @app_commands.describe(days="Days window (default 14)", limit="Max rows (default 10)")
    async def wowactive_guilds(itx: discord.Interaction, days: int = 14, limit: int = 10):
        t0 = time.time()
        await _send_defer(itx)
        window_secs = max(1, days) * 86400
        rows, prev = kpi.active_guilds(window_secs=window_secs, limit=limit)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        prev_map = {r["guild"]: r["active_members"] for r in prev} if prev else {}
        lines = []
        for r in rows:
            guild = r["guild"]
            count = r["active_members"]
            delta = None
            if guild in prev_map:
                delta = count - prev_map[guild]
            if delta is None:
                lines.append(f"{guild}: {count}")
            else:
                sign = "+" if delta >= 0 else ""
                lines.append(f"{guild}: {count} ({sign}{delta})")
        await itx.followup.send("\n".join(lines), ephemeral=True)
        _log_cmd("wowactive_guilds", t0, rows=len(rows), days=days, limit=limit)
        if format:
            await _send_serialized(itx, rows, format, "wowguilds")
        else:
            out = "\n".join([f"{r['guild']}: {r['active_members']}" for r in rows])
            await itx.followup.send(wrap_response("Most active guilds", out), ephemeral=True)
        _log_cmd("wowguilds", t0, rows=len(rows), days=days, limit=limit, fmt=format)

    @app_commands.command(name="wowah_hot", description="Most listed items on AH")
    @app_commands.describe(limit="Max rows (default 10)", format="Optional export format")
    async def wowah_hot(
        itx: discord.Interaction,
        limit: int = 10,
        format: Literal["json", "csv"] | None = None,
    ):
        t0 = time.time()
        await _send_defer(itx)
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowah_hot", t0, rows=0, limit=limit)
            return
        rows = await run_named_query("wowah_hot", limit=limit)

        with tool_context(
            "kpi_auction_hot_items",
            params={"limit": limit},
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            rows = kpi.kpi_auction_hot_items(limit=limit)
            tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        out_lines = []
        for r in rows:
            name = r.get("name") or f"Template {r['item_template']}"
            out_lines.append(
                f"{name}: {int(r['listings'])} listings, avg {copper_to_gsc(r['avg_buyout'])}"
            )
        await itx.followup.send(
            embed=rows_to_embed("Most listed items on AH", out_lines), ephemeral=True
        )
                f"{name}: {int(r['listings'])} listings, avg {kpi.copper_to_gold_s(r['avg_buyout'])}"
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
    @app_commands.describe(top="How many rows (default 20)", format="Optional export format")
    async def wowarena(
        itx: discord.Interaction,
        top: int = 20,
        format: Literal["json", "csv"] | None = None,
    ):
        t0 = time.time()
        await _send_defer(itx)

        rows = kpi.kpi_arena_rating_distribution(limit_rows=top)
        if not rows:
            return await itx.followup.send("No data.", ephemeral=True)
        lines = [f"{r['rating']}: {r['teams']}" for r in rows]
        await itx.followup.send(
            embed=rows_to_embed("Arena rating distribution", lines), ephemeral=True
        )
        if not DB_ENABLED:
            await itx.followup.send("DB is not enabled.", ephemeral=True)
            _log_cmd("wowarena", t0, rows=0, top=top)
            return
        rows = await run_named_query("wowarena", top=top)
        out = " | ".join([f"{r['rating']}:{r['teams']}" for r in rows]) if rows else "No data."
        await itx.followup.send(out, ephemeral=True)
        _log_cmd("wowarena", t0, rows=len(rows), top=top)
        with tool_context(
            "kpi_arena_rating_distribution",
            params={"top": top},
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            rows = kpi.kpi_arena_rating_distribution(limit_rows=top)
            tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))

        if format:
            await _send_serialized(itx, rows, format, "wowarena")
        else:
            # Try to render a bracketed histogram embed if data includes 'bracket' and 'rating'
            def _build_embed(rws: list[dict]) -> discord.Embed | None:
                have_bracket = rws and "bracket" in rws[0]
                have_rating = rws and "rating" in rws[0]
                have_teams = rws and "teams" in rws[0]
                if not (have_bracket and have_rating and have_teams):
                    return None

                brackets = {2: "2v2", 3: "3v3", 5: "5v5"}
                grouped: dict[int, list[dict]] = {b: [] for b in brackets}
                for r in rws:
                    b = r.get("bracket")
                    if b in grouped:
                        grouped[b].append(r)
                for lst in grouped.values():
                    lst.sort(key=lambda x: x["rating"], reverse=True)

                def _hist(lst: list[dict]) -> str:
                    if not lst:
                        return "No data"
                    sub = lst[:top]
                    max_n = max((r["teams"] for r in sub), default=1) or 1
                    lines = []
                    for r in sub:
                        blocks = max(1, int(r["teams"] / max_n * 10))
                        bar = "▉" * blocks
                        lines.append(f"{r['rating']}: {bar} ({r['teams']})")
                    return "\n".join(lines)

                embed = discord.Embed(title="Arena rating distribution")
                for b, label in brackets.items():
                    embed.add_field(name=label, value=_hist(grouped[b]), inline=False)
                return embed

            embed = _build_embed(rows)
            if embed:
                await itx.followup.send(embed=embed, ephemeral=True)
            else:
                out = " | ".join([f"{r.get('rating', '?')}:{r.get('teams', '?')}" for r in rows]) if rows else "No data."
                await itx.followup.send(wrap_response("Arena rating distribution", out), ephemeral=True)

        _log_cmd("wowarena", t0, rows=len(rows), top=top, fmt=format)

    @app_commands.command(name="wowprof", description="Profession counts ≥ threshold (skill_id, min_value)")
    @app_commands.describe(
        skill_id="Profession name or skill id (e.g., Enchanting or 333)",
        min_value="Min value (default 225)",
    )
    async def wowprof(itx: discord.Interaction, skill_id: str, min_value: int = 225):
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
        sid = sq.resolve_skill_id(skill_id)
        if sid is None:
            await itx.followup.send("Unknown profession.", ephemeral=True)
            return
        n = sq.profession_counts(skill_id=sid, min_value=min_value)
        await itx.followup.send(
            f"🛠️ Skill {sid} ≥ {min_value}: **{n}** characters",
            ephemeral=True,
        )
        _log_cmd("wowprof", t0, rows=1, skill_id=sid, min_value=min_value)
        skill_id="Profession skill id (e.g., Enchanting=333)",
        min_value="Min value (default 300)",
        format="Optional export format",


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
    tree.add_command(wowactive_guilds)
    tree.add_command(wowah_hot)
    tree.add_command(wowarena)
    tree.add_command(wowprof)
    tree.add_command(wowfactions)
    tree.add_command(wowraceclass)
    tree.add_command(wowactive_guilds)

    @app_commands.command(name="wowfind_char", description="Find characters by name (partial match)")
    @app_commands.describe(
        name="Name or part of name",
        limit="Max rows (default 10)",
        format="Optional export format",
    )
    async def wowfind_char(
        itx: discord.Interaction,
        name: str,
        limit: int = 10,
        format: Literal["json", "csv"] | None = None,
    ):
        t0 = time.time()
        await _send_defer(itx)
        with tool_context(
            "kpi_find_characters",
            params={"name": name, "limit": limit},
            guild_id=itx.guild_id,
            channel_id=itx.channel_id,
            user_id=itx.user.id,
        ) as tlog:
            try:
                rows = kpi.kpi_find_characters(name, limit=max(1, min(50, limit)))
                tlog(rows=len(rows), cache_hit=getattr(kpi, "last_cache_hit", False))
            except Exception as e:
                tlog(error=str(e), db_timeout="timeout" in str(e).lower())
                rows = []
        if not rows:
            await itx.followup.send("No characters found.", ephemeral=True)
            return
        lines = []
        for r in rows:
            online = "🟢" if r.get("online") else "⚫"
            guild = r.get("guild") or "(no guild)"
            lines.append(f"{online} {r['name']} (Lv {r['level']}) — {guild}")
        await itx.followup.send(
            embed=rows_to_embed("Characters", lines), ephemeral=True
        )
        _log_cmd("wowfind_char", t0, rows=len(rows), query=name, limit=limit)

        if format:
            await _send_serialized(itx, rows, format, "wowfind_char")
        else:
            lines = []
            for r in rows:
                online = "🟢" if r.get("online") else "⚫"
                guild = r.get("guild") or "(no guild)"
                lines.append(f"{online} {r['name']} (Lv {r['level']}) — {guild}")
            await itx.followup.send(
                wrap_response("Characters found", "\n".join(lines)), ephemeral=True
            )
        _log_cmd("wowfind_char", t0, rows=len(rows), query=name, limit=limit, fmt=format)

    tree.add_command(wowfind_char)
