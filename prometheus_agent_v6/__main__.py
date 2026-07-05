"""Module entrypoint for python -m prometheus_agent_v6."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
