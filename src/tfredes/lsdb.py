
import time

from pacotes import PacLSP
from estruturas import EntradaLSDB
from logs import Logs

TIMEOUT_LSP = 90


class GerenciadorLSDB:
    def __init__(
        self,
        endereco_virtual: str,
        logs: Logs
    ):
        self.endereco_virtual = endereco_virtual #do proprio roteador
        self.logs = logs

        self.lsdb: dict[str, EntradaLSDB] = {} #chave endereco virtual da origem

    def registrar_lsp_proprio( 
        #chamar quando:
        # - um vizinho se torna ativo ou inativo;
        # - periodicamente, a cada 30 segundos (renovação), mesmo sem mudança.

        #O número de sequência é definido pelo Roteador, não pelo gerenciador
        self,
        lsp: PacLSP,
        agora: float | None = None
    ) -> None:
        if agora is None:
            agora = time.monotonic()

        if lsp.origem != self.endereco_virtual:
            raise ValueError("O LSP não pertence a este roteador.")

        self.lsdb[lsp.origem] = EntradaLSDB(
            lsp = lsp,
            ultimo_recebimento = agora
        )

        self.logs.criaLog(
            "LSDB",
            f"LSP próprio registrado. Sequência: {lsp.sequencia}."
        )

    def processar_lsp(
        self,
        lsp: PacLSP,
        agora: float | None = None
    ) -> bool:
        #chamar quando:
        # - vier de outro roteador

        if agora is None:
            agora = time.monotonic()

        if lsp.origem == self.endereco_virtual:
            return False

        entrada_atual = self.lsdb.get(lsp.origem)

        if entrada_atual is not None:
            sequencia_atual = entrada_atual.lsp.sequencia

            if lsp.sequencia <= sequencia_atual:
                return False

        # novo
        self.lsdb[lsp.origem] = EntradaLSDB(
            lsp=lsp,
            ultimo_recebimento=agora
        )

        self.logs.criaLog(
            "LSDB",
            f"LSP de {lsp.origem} atualizado. "
            f"Sequência: {lsp.sequencia}."
        )

        return True

    def remover_expirados( #remove lsps expirados
        self,
        agora: float | None = None
    ) -> list[str]:
        if agora is None:
            agora = time.monotonic()

        origens_removidas = []

        for origem, entrada in list(self.lsdb.items()):

            #nao precisa pq e um dicionario, acaba atualizando na rotina
            if origem == self.endereco_virtual:
                continue

            tempo_sem_atualizacao = agora - entrada.ultimo_recebimento

            if tempo_sem_atualizacao >= TIMEOUT_LSP:
                del self.lsdb[origem]
                origens_removidas.append(origem)

                self.logs.criaLog(
                    "LSDB",
                    f"LSP de {origem} expirou e foi removido."
                )

        return origens_removidas

    def obter_lsp(
        self,
        origem: str
    ) -> PacLSP | None:
        entrada = self.lsdb.get(origem)

        if entrada is None:
            return None

        return entrada.lsp

    def obter_todos_lsps(self) -> list[PacLSP]:
        lsps = []
        for entrada in self.lsdb.values():
            lsps.append(entrada.lsp)
        return lsps
