import time, json, io
import discord
from discord import app_commands
from utils.formatters import kv_to_embed, copper_to_gsc
from utils.charts import generate_insights_chart
import ac_metrics as kpi


async def _send_defer(itx: discord.Interaction):
    if not itx.response.is_done():
        await itx.response.defer(thinking=True, ephemeral=True)


def _fmt_population(pop: dict) -> list[tuple[str, str]]:
    return [
        ("Online", str(pop.get("total", 0))),
        ("Alliance", f"{pop.get('alliance', 0)} ({pop.get('alliance_pct', 0)}%)"),
        ("Horde", f"{pop.get('horde', 0)} ({pop.get('horde_pct', 0)}%)"),
    ]


def _fmt_concurrency(cc: dict) -> list[tuple[str, str]]:
    peak_time = cc.get("peak_time")
    if peak_time:
        try:
            peak_time_s = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(peak_time)))
        except Exception:
            peak_time_s = str(peak_time)
    else:
        peak_time_s = "—"
    return [
        ("Current", str(cc.get("current", 0))),
        ("p95 (24h)", str(cc.get("p95", 0))),
        ("Peak (24h)", f"{cc.get('peak', 0)} @ {peak_time_s}"),
    ]


def _fmt_economy(e: dict) -> list[tuple[str, str]]:
    return [
        ("Total Gold", copper_to_gsc(int(e.get("total_copper", 0)))),
        ("Per Player", copper_to_gsc(int(e.get("per_capita_copper", 0)))),
        ("Population", str(e.get("population", 0))),
    ]


def _fmt_auctions(a: dict) -> list[tuple[str, str]]:
    return [
        ("Active Auctions", str(a.get("active", 0))),
        (
            "Avg Buyout",
            copper_to_gsc(int(a.get("avg_buyout_copper", 0))) if a.get("avg_buyout_copper") else "—",
        ),
    ]


def _fmt_stability(s: dict) -> list[tuple[str, str]]:
    return [
        ("Uptime (hrs)", str(s.get("uptime_hours") or "—")),
    ]


def setup_insights(tree: app_commands.CommandTree):
    @app_commands.command(name="insights", description="Realm insights: population, concurrency, economy, auctions, stability")
    @app_commands.describe(chart="Attach a chart image (sparkline + bars)")
    async def insights_cmd(itx: discord.Interaction, chart: bool = False):
        # Always defer immediately for time budget safety
        try:
            if not itx.response.is_done():
                await itx.response.defer(thinking=True, ephemeral=True)
        except Exception:
            pass
        # Compute insights
        try:
            data = kpi.get_insights()
        except Exception as e:
            try:
                await itx.followup.send(f"⚠️ Failed to compute insights: {e}", ephemeral=True)
            except Exception:
                pass
            return

        embed = discord.Embed(title="Realm Insights", color=0x3498DB)
        pop = data.get("population") or {}
        cc = data.get("concurrency") or {}
        eco = data.get("economy") or {}
        auc = data.get("auctions") or {}
        stb = data.get("stability") or {}
        for title, items in (
            ("Population", _fmt_population(pop)),
            ("Concurrency", _fmt_concurrency(cc)),
            ("Economy", _fmt_economy(eco)),
            ("Auctions", _fmt_auctions(auc)),
            ("Stability", _fmt_stability(stb)),
        ):
            value = "\n".join(f"**{k}:** {v}" for k, v in items)
            embed.add_field(name=title, value=value or "—", inline=False)
        try:
            if chart:
                try:
                    png = generate_insights_chart(data)
                    file = discord.File(io.BytesIO(png), filename="insights.png")
                except Exception:
                    file = None
            else:
                file = None
            await itx.followup.send(embed=embed, file=file, ephemeral=True)
        except Exception:
            # Final fallback: try whichever channel isn't used yet
            try:
                await itx.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass

    tree.add_command(insights_cmd)
