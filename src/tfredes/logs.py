
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import sys


class Logs:
    """Classe para gerenciar logs do sistema."""

    def __init__(self, caminho_arquivo: str | Path | None = None, stderr: bool = False):
        self.caminho_arquivo = Path(caminho_arquivo) if caminho_arquivo else None
        self.stderr = stderr
        self.on_log: Callable[[str], None] | None = None

    def criaLog(self, categoria: str, mensagem: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{categoria}] {mensagem}"

        if self.caminho_arquivo is not None:
            with self.caminho_arquivo.open("a", encoding="utf-8") as f:
                f.write(linha + "\n")

        if self.on_log is not None:
            self.on_log(linha)

        if self.stderr or (self.caminho_arquivo is None and self.on_log is None):
            print(linha, file=sys.stderr)
