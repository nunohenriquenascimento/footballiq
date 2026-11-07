"""Entry point para executar o pacote com python -m footballiq."""

from .etl import main

if __name__ == "__main__":
    raise SystemExit(main())
