"""CLI entry point.

Run from ``backend/``::

    python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx"
    python -m scripts.mypaisaa_fetch --dry-run                  # validate input only
    python -m scripts.mypaisaa_fetch --limit 10                 # controlled test run
    python -m scripts.mypaisaa_fetch --retry-failed             # reprocess failures only
    python -m scripts.mypaisaa_fetch --force                    # reprocess everything
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import load_config
from .logging_utils import get_logger
from .pipeline import run_pipeline

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mypaisaa_fetch",
        description="Fetch ALL MyPaisaa bank statements for a list of user IDs.",
    )
    parser.add_argument(
        "--input",
        help="CSV/XLSX with user IDs (default: New Dataset/users.csv; "
        "use the provided 'PS ids for users.xlsx' for the full dataset)",
    )
    parser.add_argument("--output-dir", help="Directory for statements + manifest + reports")
    parser.add_argument("--max-concurrent", type=int, help="Parallel users (default 5)")
    parser.add_argument("--max-retries", type=int, help="Retries per request (default 3)")
    parser.add_argument("--timeout", type=float, help="Request timeout seconds (default 60)")
    parser.add_argument(
        "--requests-per-second", type=float,
        help="Global pacing; 0 disables (default from env REQUESTS_PER_SECOND)",
    )
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Process only the first N users (controlled test runs)",
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Reprocess only users/statements that previously failed",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess every user and re-download every statement",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate the input file and show counts without calling the API",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(
        input_file=args.input,
        output_dir=args.output_dir,
        max_concurrent_users=args.max_concurrent,
        max_retries=args.max_retries,
        request_timeout_seconds=args.timeout,
        requests_per_second=args.requests_per_second,
    )

    logger.info(
        "run started",
        input=str(config.input_file),
        output=str(config.output_dir),
        max_concurrent_users=config.max_concurrent_users,
        max_retries=config.max_retries,
        requests_per_second=config.requests_per_second,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    pipeline, stats = asyncio.run(
        run_pipeline(
            config,
            retry_failed=args.retry_failed,
            force=args.force,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    )

    print("\n" + pipeline.summary_text())
    return 1 if pipeline.has_failures() else 0


if __name__ == "__main__":
    sys.exit(main())
