# Read-only Grants

The SQL script at `sql/create_readonly_grants.sql` creates a database user with read-only access.
Run the verification script to ensure it grants only `SELECT` privileges:

```
python scripts/verify_readonly_grants.py
```

The check fails if any non-read-only privilege is detected.
