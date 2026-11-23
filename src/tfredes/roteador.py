


import asyncio
import socket
import time

from config.config import Config
from tfredes.logs import Logs
from tfredes.lsdb import GerenciadorLSDB
from tfredes.pacotes import (
        PacDados, PacHello, PacICMP, PacLSP, Pacote,
        TipoICMP, desserializar_pacote, serializar_pacote,
    )
from tfredes.vizinhos import GerenciadorVizinhos
from tfredes.estruturas import EntradaRota, PingPendente

class Roteador:
    def __init__(self, config: Config, logs: Logs):
        self.config = config
        self.logs = logs
        self.gerenciador_vizinhos = GerenciadorVizinhos(config, logs)
        self.gerenciador_lsdb = GerenciadorLSDB(config.virtual_ip, logs)
        self.socket_udp = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.socket_udp.setblocking(False)
        self.socket_udp.bind(("0.0.0.0", config.udp_port))

        self.sequencia_lsp: int = int(time.time())  


    async def run(self):
        self.gerar_novo_lsp()  # Gera o LSP inicial do roteador

        tarefas_fundo = [
                asyncio.create_task(self.receber_pacotes()),
                asyncio.create_task(self.loop_hello()),
                asyncio.create_task(self.loop_monitorar_vizinhos()),
                asyncio.create_task(self.loop_envelhecimento_lsdb()),
                asyncio.create_task(self.loop_renovacao_lsp()),
            ]
        try:
            await self.interface_usuario()
        finally:
            for t in tarefas_fundo:
                t.cancel()
            await asyncio.gather(*tarefas_fundo, return_exceptions=True)
            self.socket_udp.close()

    async def interface_usuario(self):
        while True:
            await asyncio.sleep(0.1)  # Pequena pausa para evitar uso excessivo de CPU

    def enviar_pacote(self, pacote: Pacote, ip: str, porta: int) -> None:
            self.socket_udp.sendto(serializar_pacote(pacote), (ip, porta))

    def gerar_lsp_proprio(self) -> PacLSP:
        self.sequencia_lsp += 1
        vizinhos_ativos = {
            v.endereco_virtual: v.custo
            for v in self.gerenciador_vizinhos.obter_vizinhos_ativos()
        }
        return PacLSP(
            origem=self.config.virtual_ip,
            sequencia=self.sequencia_lsp,
            vizinhos=vizinhos_ativos,
        )

    def gerar_novo_lsp(self) -> None:
        lsp = self.gerar_lsp_proprio()
        self.gerenciador_lsdb.registrar_lsp_proprio(lsp)
        # self.recalcular_tabela()
        self.inundar_lsp(lsp)

    def inundar_lsp(self, lsp: PacLSP, excluir_endereco: tuple[str, int] | None = None) -> None:
        for vizinho in self.gerenciador_vizinhos.obter_vizinhos_ativos():
            if excluir_endereco is not None and (vizinho.ip, vizinho.porta) == excluir_endereco:
                continue
            self.enviar_pacote(lsp, vizinho.ip, vizinho.porta)

    async def receber_pacotes(self):

        loop = asyncio.get_running_loop()

        while True:
            dados, endereco = await loop.sock_recvfrom(
                self.socket_udp, 4096
            )

            self.processar_pacote(dados, endereco)


    async def loop_hello(self):
        while True:

            for vizinho in self.gerenciador_vizinhos.vizinhos.values():
                pacote_hello = PacHello(endereco_virtual=self.config.virtual_ip) 
                self.enviar_pacote(pacote_hello, vizinho.ip, vizinho.porta)

            await asyncio.sleep(5)

    async def loop_monitorar_vizinhos(self):
        while True:

            inativos = self.gerenciador_vizinhos.verificar_timeouts()

            if inativos:
                self.gerar_novo_lsp()

            await asyncio.sleep(1)

    async def loop_envelhecimento_lsdb(self):

        while True:

            removidos = self.gerenciador_lsdb.remover_expirados()

            if removidos:
                self.recalcular_tabela()

            await asyncio.sleep(1)

    async def loop_renovacao_lsp(self):

        while True:

            await asyncio.sleep(30)

            lsp = self.gerar_lsp_proprio()

            self.gerenciador_lsdb.registrar_lsp_proprio(lsp)

            self.inundar_lsp(lsp)