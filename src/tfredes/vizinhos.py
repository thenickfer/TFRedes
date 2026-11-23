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

    def processar_hello(
        self,
        endereco_virtual: str,
        agora: float | None = None #se precisar testar usa um valor, se nao chama so com endereco
    ) -> bool: #retorna true se o estado do vizinho mudou (ativo/inativo)
        if agora is None:
            agora = time.monotonic()

        vizinho = self.vizinhos.get(endereco_virtual)

        # TODO: precisa ignorar se nao estiver configurado?
        if vizinho is None:
            return False

        vizinho.ultimo_hello = agora

        if vizinho.ativo:
            return False

        vizinho.ativo = True # Primeiro HELLO

        self.logs.criaLog(
            "VIZINHOS",
            f"Vizinho {endereco_virtual} ficou ativo."
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
