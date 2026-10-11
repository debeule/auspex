"""Command line for the strategy service.

`python -m auspex_strategy kill [--strategy NAME] [--reason TEXT] [--reset]` sets or clears a
kill switch in MinIO directly, without Docker or the runtime, so it works while the stack is
degraded. It reads `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` from the
environment.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence

from minio import Minio

from auspex_strategy.risk.kill_switch import KillSwitch
from auspex_strategy.runtime.store import MinioObjectStore


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(prog="python -m auspex_strategy")
    commands = parser.add_subparsers(dest="command", required=True)
    kill = commands.add_parser(
        "kill",
        help="stop new intents for every strategy, or for one",
        description="Turn a kill switch on (or off with --reset). Open positions are not "
                    "closed; they exit on their own conditions.",
    )
    kill.add_argument("--strategy", help="only this strategy (default: all strategies)")
    kill.add_argument("--reason", default="set from the command line",
                      help="why, recorded with the trigger or reset")
    kill.add_argument("--reset", action="store_true", help="turn the switch off")
    args = parser.parse_args(argv)

    missing = [name for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
               if not env.get(name)]
    if missing:
        parser.error(f"set {', '.join(missing)} in the environment")
    minio = Minio(env["MINIO_ENDPOINT"], access_key=env["MINIO_ACCESS_KEY"],
                  secret_key=env["MINIO_SECRET_KEY"], secure=False)
    switch = KillSwitch(MinioObjectStore(minio))
    scope = args.strategy or "all strategies"
    if args.reset:
        switch.reset(args.reason, args.strategy)
        print(f"kill switch reset for {scope}")
    else:
        switch.trigger(args.reason, args.strategy)
        print(f"kill switch on for {scope}: {args.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
