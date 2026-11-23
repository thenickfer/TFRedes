import argparse
import asyncio
from pathlib import Path
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



def _resolver_caminho_config(valor: str) -> Path:
    caminho = Path(valor)
    if caminho.exists():
        return caminho

    nome = f"r{valor}" if valor.isdigit() else valor
    if not nome.endswith(".yaml"):
        nome = f"{nome}.yaml"

    base = Path(__file__).resolve().parent / "roteadores"
    candidatos = [
        base / "r1" / nome,
        base / Path(nome).stem / nome,
        base / nome,
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato

    return caminho


async def _main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inicia um roteador a partir de um número ou arquivo YAML.")
    parser.add_argument(
        "config",
        nargs="?",
        default="1",
        help="Número do roteador (ex: 1, 2, 3, 4) ou caminho para o YAML (padrão: 1)",
    )
    args = parser.parse_args(argv)
    config_path = _resolver_caminho_config(args.config)

    try:
        config = load_config(config_path)
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    roteador = Roteador(config, Logs(
        caminho_arquivo=config_path.with_suffix(".log"),
        stderr=False,
    ))
    await roteador.run()

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(argv))

if __name__ == "__main__":
    sys.exit(main())
