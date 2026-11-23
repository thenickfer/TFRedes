import argparse
import asyncio
from socket import socket
import sys

from tfredes.logs import Logs
from tfredes.lsdb import GerenciadorLSDB
from tfredes.pacotes import PacHello, PacHello, Pacote, serializar_pacote
from tfredes.roteador import Roteador
from tfredes.vizinhos import GerenciadorVizinhos

try:
    from config.config import load_config
except ImportError:
    from src.config.config import load_config



async def _main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load node configuration from a YAML file.")
    parser.add_argument(
        "config",
        nargs="?",
        default="r1.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    roteador = Roteador(config, Logs())
    await roteador.run()

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(argv))

if __name__ == "__main__":
    asyncio.run(main())
