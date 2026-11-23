import time

from config import Config
from tfredes.estruturas import EstadoVizinho
from tfredes.logs import Logs

INTERVALO_HELLO = 5 #para manar
TIMEOUT_VIZINHO = 20 #para receber (hello)

class GerenciadorVizinhos:
    def __init__(
        self,
        config: Config,
        logs: Logs
    ):
        self.logs = logs

        # Guarda os vizinhos configurados, incluindo inativos
        self.vizinhos: dict[str, EstadoVizinho] = {} #chave: endereco virtual

        for endereco_virtual, vizinho_config in config.neighbors.items():
            self.vizinhos[endereco_virtual] = EstadoVizinho(
                endereco_virtual = endereco_virtual,
                ip = vizinho_config.ip,
                porta = vizinho_config.udp_port,
                custo = vizinho_config.cost
            )

    def endereco_eh_vizinho(self, endereco: tuple[str, int]) -> bool:
        ip, porta = endereco
        for vizinho in self.vizinhos.values():
            if vizinho.ip == ip and vizinho.porta == porta:
                return True
        return False

    def obter_vizinho_por_endereco_real(
        self,
        endereco: tuple[str, int]
    ) -> EstadoVizinho | None:
        ip, porta = endereco
        for vizinho in self.vizinhos.values():
            if vizinho.ip == ip and vizinho.porta == porta:
                return vizinho
        return None

    def processar_hello(
        self,
        endereco_virtual: str,
        endereco_real: tuple[str, int] | None = None,
        agora: float | None = None
    ) -> bool:
        if agora is None:
            agora = time.monotonic()

        vizinho: EstadoVizinho | None = None
        if endereco_real is not None:
            vizinho = self.obter_vizinho_por_endereco_real(endereco_real)
            if vizinho is None:
                return False
            # B3: associa endereço virtual -> (IP real, porta) do pacote recebido
            if vizinho.endereco_virtual != endereco_virtual:
                self.vizinhos.pop(vizinho.endereco_virtual, None)
                vizinho.endereco_virtual = endereco_virtual
                self.vizinhos[endereco_virtual] = vizinho
            vizinho.ip, vizinho.porta = endereco_real
        else:
            vizinho = self.vizinhos.get(endereco_virtual)
            if vizinho is None:
                return False

        vizinho.ultimo_hello = agora

        if vizinho.ativo:
            return False

        vizinho.ativo = True

        self.logs.criaLog(
            "VIZINHOS",
            f"Vizinho {endereco_virtual} ({vizinho.ip}:{vizinho.porta}) ficou ativo."
        )

        return True

    def verificar_timeouts(
        self,
        agora: float | None = None #igual o de cima
    ) -> list[str]:

        if agora is None:
            agora = time.monotonic()

        vizinhos_inativos = []

        for endereco_virtual, vizinho in self.vizinhos.items():
            if not vizinho.ativo: #se ta inativo nao tem como dar timeout
                continue

            tempo_sem_hello = agora - vizinho.ultimo_hello

            if tempo_sem_hello >= TIMEOUT_VIZINHO:
                vizinho.ativo = False

                vizinhos_inativos.append(endereco_virtual)

                self.logs.criaLog(
                    "VIZINHOS",
                    f"Vizinho {endereco_virtual} ficou inativo "
                    f"por falta de HELLO."
                )

        return vizinhos_inativos

    def obter_vizinhos_ativos(self) -> list[EstadoVizinho]:
        ativos = []
        for vizinho in self.vizinhos.values():
            if vizinho.ativo:
                ativos.append(vizinho)
        return ativos

    def obter_vizinho(
        self,
        endereco_virtual: str
    ) -> EstadoVizinho | None:
        return self.vizinhos.get(endereco_virtual)
