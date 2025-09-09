import discord
from discord import app_commands
import pymysql
import ac_metrics as kpi
from utils.tool_logging import get_last_error


def setup_health(tree: app_commands.CommandTree):
    @app_commands.command(name="health", description="Report DB pool and cache status")
    async def health_cmd(itx: discord.Interaction):
        db_status = "disabled"
        if kpi.DB_USER:
            try:
                pymysql.connect(
                    host=kpi.DB_HOST,
                    port=kpi.DB_PORT,
                    user=kpi.DB_USER,
                    password=kpi.DB_PASS,
                    database=kpi.DB_CHAR,
                    connect_timeout=2,
                ).close()
                db_status = "ok"
            except Exception as e:
                db_status = f"error: {type(e).__name__}"
        caches = {"metrics": len(kpi._cache)}
        rag = getattr(itx.client, "_rag", None)
        if rag:
            caches["kb"] = len(getattr(rag, "kb", []))
            caches["docs"] = len(getattr(rag, "docs", []))
        lines = [f"DB: {db_status}"]
        for k, v in caches.items():
            lines.append(f"cache_{k}: {v}")
        err = get_last_error() or "none"
        lines.append(f"last_error: {err}")
        await itx.response.send_message("\n".join(lines), ephemeral=True)

    tree.add_command(health_cmd)
