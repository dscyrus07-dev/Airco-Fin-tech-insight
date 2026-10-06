"""Look up stored statement metadata (incl. passwords) for a user.

The fetch pipeline never prints passwords in logs or reports, but the
passwords ARE stored locally in manifest.db so you can open the PDFs.
This command is the deliberate, explicit way to retrieve one:

    cd backend
    python -m scripts.mypaisaa_fetch.lookup 656296
    python -m scripts.mypaisaa_fetch.lookup 656296 --file statement_002.pdf

Only run it for users you are authorised to access.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .manifest import Manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lookup", description="Show stored statement passwords for one user."
    )
    parser.add_argument("user_id", help="MyPaisaa user ID")
    parser.add_argument("--file", help="Only show this file (e.g. statement_002.pdf)")
    args = parser.parse_args(argv)

    config = load_config()
    manifest = Manifest(config.output_dir / "manifest.db")
    rows = manifest.statements_for_user(args.user_id)
    manifest.close()
    if not rows:
        print(f"No statements found for user {args.user_id}")
        return 1

    print(f"{'file':<22} {'status':<18} {'password':<20} original filename")
    print("-" * 100)
    for row in rows:
        filename = row["filename"] or "-"
        if args.file and filename != args.file:
            continue
        password = row["password"] if row["password_available"] else "(none given)"
        if row["password_verified"]:
            password += "  [verified OK]"
        elif row["download_status"] == "password_invalid":
            password += "  [WRONG - does not open]"
        elif row["download_status"] == "password_required":
            password += "  [PDF locked, no password available]"
        print(
            f"{filename:<22} {row['download_status']:<18} {password:<20} "
            f"{row['original_filename'] or ''}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
