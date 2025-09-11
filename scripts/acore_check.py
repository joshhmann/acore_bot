#!/usr/bin/env python3
"""Quick AzerothCore connectivity check.

- Loads .env
- SOAP: runs `.server info` and prints a short summary or an error
- DB (optional): prints totals if DB_ENABLED=true and creds provided
"""
from __future__ import annotations
import os
import sys

from dotenv import load_dotenv

from soap import SoapClient
from ac_db import DBConfig, get_online_count, get_totals


def main() -> int:
    load_dotenv()

    soap_host = os.getenv("SOAP_HOST", "127.0.0.1")
    soap_port = int(os.getenv("SOAP_PORT", "7878"))
    soap_user = os.getenv("SOAP_USER", "")
    soap_pass = os.getenv("SOAP_PASS", "")

    print("== SOAP check ==")
    if not soap_user or not soap_pass:
        print("Missing SOAP_USER/SOAP_PASS in .env")
    client = SoapClient(soap_host, soap_port, soap_user, soap_pass)
    try:
        out = client.execute(".server info")
        first = (out or "").splitlines()[:6]
        print("OK: .server info")
        for line in first:
            print("  ", line)
    except Exception as e:
        print("SOAP error:", client.format_error(e))

    print("\n== DB check ==")
    db_enabled = os.getenv("DB_ENABLED", "false").lower() in {"1","true","yes","on"}
    if not db_enabled:
        print("DB checks disabled (set DB_ENABLED=true)")
        return 0
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASS", "")
    auth_db = os.getenv("DB_AUTH_DB", "auth")
    char_db = os.getenv("DB_CHAR_DB", "characters")
    world_db = os.getenv("DB_WORLD_DB", "world")
    if not (user and password):
        print("Missing DB_USER/DB_PASS in .env")
        return 1
    cfg = DBConfig(host, port, user, password, auth_db, char_db, world_db)
    try:
        online = get_online_count(cfg)
        acc, chars, guilds = get_totals(cfg)
        print(f"Online: {online} | Accounts: {acc} | Characters: {chars} | Guilds: {guilds}")
    except Exception as e:
        print("DB error:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

