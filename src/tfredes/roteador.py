


import asyncio
import socket
import time

from config.config import Config
from tfredes.logs import Logs
from tfredes.lsdb import GerenciadorLSDB
from tfredes.pacotes import (
        PacDados, PacHello, PacICMP, PacLSP, PacRoteavel, Pacote,
        TipoICMP, desserializar_pacote, serializar_pacote,
    )
from tfredes.roteamento import GerenciadorRoteamento
from tfredes.trata_pacotes import Encaminhador, AcaoEncaminhamento, ResultadoEncaminhamento
from tfredes.vizinhos import GerenciadorVizinhos
from tfredes.estruturas import EntradaRota, PingPendente

class Roteador:
    def __init__(self, config: Config, logs: Logs):
        self.config = config
        self.logs = logs
        self.gerenciador_vizinhos = GerenciadorVizinhos(config, logs)
        self.gerenciador_lsdb = GerenciadorLSDB(config.virtual_ip, logs)
        self.gerenciador_roteamento = GerenciadorRoteamento(config.virtual_ip, self.gerenciador_lsdb, logs)
        self.encaminhador = Encaminhador(config.virtual_ip, self.gerenciador_roteamento, logs)
        self.pings_pendentes: dict[int, PingPendente] = {}
        self.proximo_id_pacote: int = 1 

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


    def recalcular_tabela(self) -> None:
        self.gerenciador_roteamento.recalcular_rotas()

    def enviar_pacote(self, pacote: Pacote, virtual_ip: str) -> None:
            viz = self.gerenciador_vizinhos.obter_vizinho(virtual_ip)
            if viz:
                try:
                    addr = (viz.ip, viz.porta)
                    self.socket_udp.sendto(serializar_pacote(pacote), addr)
                    self.logs.criaLog(
                        "ENVIO",
                        f"Pacote enviado para {virtual_ip} ({addr[0]}:{addr[1]})."
                    )   
                except Exception as e:
                    self.logs.criaLog(
                        "ERRO",
                        f"Erro ao enviar pacote para {virtual_ip} ({addr[0]}:{addr[1]}): {e}"
                    )
            else:
                self.logs.criaLog(
                    "ERRO",
                    f"Vizinho {virtual_ip} não encontrado na lista de vizinhos ativos."
                )

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
        self.recalcular_tabela()
        self.inundar_lsp(lsp)

    def inundar_lsp(self, lsp: PacLSP, excluir_endereco: tuple[str, int] | None = None) -> None:
        for vizinho in self.gerenciador_vizinhos.obter_vizinhos_ativos():
            if excluir_endereco is not None and (vizinho.ip, vizinho.porta) == excluir_endereco:
                continue
            self.enviar_pacote(lsp, vizinho.endereco_virtual)

    async def receber_pacotes(self):

        loop = asyncio.get_running_loop()

        while True:
            try:
                dados, endereco = await loop.sock_recvfrom(
                    self.socket_udp, 4096
                )

                self.processar_pacote(dados, endereco)
            except Exception as e:
                self.logs.criaLog(
                    "ERRO",
                    f"Erro ao receber pacote: {e}"
                )
                continue

    def processar_pacote(self, dados: bytes, endereco: tuple[str, int]) -> None:
        pacote = desserializar_pacote(dados)

        if pacote is None:
            self.logs.criaLog(
                "ERRO",
                f"Pacote inválido recebido de {endereco[0]}:{endereco[1]}"
            )
            return

        if isinstance(pacote, PacHello):
            self.logs.criaLog(
                "HELLO",
                f"Hello recebido de {pacote.endereco_virtual} "
                f"({endereco[0]}:{endereco[1]})."
            )
            if self.gerenciador_vizinhos.processar_hello(pacote.endereco_virtual):
                self.gerar_novo_lsp()
                for lsp in self.gerenciador_lsdb.obter_todos_lsps():
                    if lsp.origem != self.config.virtual_ip:
                        self.enviar_pacote(lsp, pacote.endereco_virtual)

        elif isinstance(pacote, PacLSP):
            self.logs.criaLog(
                "LSDB",
                f"LSP recebido de {pacote.origem} com sequência {pacote.sequencia}."
            )
            if self.gerenciador_lsdb.processar_lsp(pacote):
                self.recalcular_tabela()
                self.inundar_lsp(pacote, excluir_endereco=endereco)
        elif isinstance(pacote, PacRoteavel):
            self.logs.criaLog(
                "ROTEAVEL",
                f"Pacote roteável recebido de {pacote.origem} "
                f"com destino {pacote.destino}."
            )
            resultado = self.encaminhador.processar_pacote_recebido(pacote)
            if resultado:
                self.exec_acao(resultado)

    def exec_acao(self, resultado: ResultadoEncaminhamento) -> None:
        if resultado.acao == AcaoEncaminhamento.DESCARTAR:
            self.logs.criaLog(
                "DESCARTAR",
                f"Pacote descartado. Observações: {resultado.observacoes}"
            )
        elif resultado.acao in(
            AcaoEncaminhamento.ICMP_GERADO,
            AcaoEncaminhamento.RESPOSTA_ECO,
            ):
            if isinstance(resultado.pacote, PacICMP):
                res_envio = self.encaminhador.preparar_pacote_originado(resultado.pacote)
                self.exec_acao(res_envio)
                if res_envio.acao == AcaoEncaminhamento.ENCAMINHAR:
                    self.logs.criaLog(
                        "ICMP",
                        f"Mensagem ICMP({resultado.pacote.tipo}) enviada para {resultado.pacote.destino}."
                    )
        elif resultado.acao == AcaoEncaminhamento.ENCAMINHAR:
            if resultado.pacote and resultado.proximo_salto:
                self.enviar_pacote(resultado.pacote, resultado.proximo_salto)
                self.logs.criaLog(
                    "ENCAMINHAR",
                    f"Pacote encaminhado para {resultado.proximo_salto}."
                )
        elif resultado.acao == AcaoEncaminhamento.RESULTADO_ICMP:
            if isinstance(resultado.pacote, PacICMP):
                pkg = resultado.pacote
                tipo = TipoICMP(int(pkg.tipo))

                if tipo == TipoICMP.ECHO_REPLY:
                    pendente = self.pings_pendentes.pop(pkg.id, None)
                    if pendente is not None:
                        rtt = (time.monotonic() - pendente.horario_envio) * 1000
                        self.logs.criaLog(                                                                                                                           
                        "PING",
                        f"Resposta de {pkg.origem}: id={pkg.id} ttl={pkg.ttl} tempo={rtt:.2f}ms"                                                              
                    )
                    else:
                        self.logs.criaLog(                                                                                                                           
                            "ICMP",
                            f"ECHO_REPLY inesperado de {pkg.origem} (id={pkg.id})."
                        )
                elif tipo == TipoICMP.TEMPO_EXCEDIDO:
                    self.pings_pendentes.pop(pkg.id, None)                                                                                                           
                    self.logs.criaLog(                                                                                                                               
                        "ICMP",
                        f"Tempo excedido (TTL=0) reportado por {pkg.origem} (id={pkg.id})."
                    )

                elif tipo == TipoICMP.DESTINO_INACESSIVEL:                                                                                                           
                    self.pings_pendentes.pop(pkg.id, None)                                                                                                           
                    self.logs.criaLog(                                                                                                                               
                        "ICMP",
                        f"Destino inacessível reportado por {pkg.origem} (id={pkg.id})."
                    )
        elif resultado.acao == AcaoEncaminhamento.DESTINO_INALCANCAVEL:
            self.logs.criaLog(
                "ICMP",
                f"Destino inalcançável. Observações: {resultado.observacoes}"
            )

        elif resultado.acao == AcaoEncaminhamento.ENTREGA_DADOS:
            if isinstance(resultado.pacote, PacDados):
                self.logs.criaLog(
                    "ENTREGA",
                    f"Pacote entregue localmente. Destino: {resultado.pacote.destino if resultado.pacote else 'N/A'}.\n Mensagem: {resultado.pacote.mensagem if resultado.pacote else 'N/A'}"
                )

    async def loop_hello(self):
        while True:

            for vizinho in self.gerenciador_vizinhos.vizinhos.values():
                pacote_hello = PacHello(endereco_virtual=self.config.virtual_ip) 
                self.enviar_pacote(pacote_hello, vizinho.endereco_virtual)

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