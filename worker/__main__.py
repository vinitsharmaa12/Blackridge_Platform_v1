"""Entrypoint: python -m worker"""
from worker.scheduler import main

if __name__ == "__main__":
    raise SystemExit(main())
