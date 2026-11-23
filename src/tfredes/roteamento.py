
import heapq

from estruturas import EntradaRota
from lsdb import GerenciadorLSDB
from logs import Logs


class GerenciadorRoteamento:
    def __init__(
        self,
        endereco_virtual: str,
        lsdb: GerenciadorLSDB,
        logs: Logs
    ):
        self.endereco_virtual = endereco_virtual
        self.lsdb = lsdb
        self.logs = logs

        self.tabela: dict[str, EntradaRota] = {} #chave end virtual destino

    def recalcular_rotas(self) -> None:
        #(re)constrou o grafo, chama o dijkstra e atualiza tabela

        #nao vou criar classe nodo nao
        #exemplo de como fica:
        #grafo = {
        #   "10.5.1.1": {
        #        "10.5.2.1": 3,
        #        "10.5.3.1": 5
        #    },
        #   "10.5.2.1": {
        #       "10.5.1.1": 3,
        #       "10.5.4.1": 2
        #   },
        #   "10.5.3.1": {},
        #   "10.5.4.1": {}
        #}
        #de forma simples: grafo[origem][destino] = custo
        grafo: dict[str, dict[str, int]] = {}

        for lsp in self.lsdb.obter_todos_lsps():

            grafo.setdefault(lsp.origem, {}) #garante que o roteador de origem exista no grafo

            for vizinho, custo in lsp.vizinhos.items():
                grafo[lsp.origem][vizinho] = custo

                grafo.setdefault(vizinho, {}) #garante que o vizinho também exista como vértice,

        # chama o dijkstra
        distancias, proximos_saltos = self._dijkstra(grafo)

        nova_tabela: dict[str, EntradaRota] = {}

        for destino, custo in distancias.items():

            if destino == self.endereco_virtual: #nao precisa rot pra si mesmo
                continue

            proximo_salto = proximos_saltos.get(destino)

            if proximo_salto is None:
                continue

            nova_tabela[destino] = EntradaRota(
                rede_destino=destino,
                proximo_salto=proximo_salto,
                custo=custo
            )

        self.tabela = nova_tabela

        self.logs.criaLog(
            "ROTEAMENTO",
            f"Tabela de rotas recalculada. "
            f"{len(self.tabela)} destinos alcançáveis."
        )

    def _dijkstra(
        self,
        grafo: dict[str, dict[str, int]]
    ) -> tuple[dict[str, int], dict[str, str]]:
        origem = self.endereco_virtual

        distancias = {origem: 0} #dict
        proximos_saltos = {}

        fila = [(0, origem)] # (custo acumulado, endereço virtual)

        while len(fila) > 0:
            custo_atual, atual = heapq.heappop(fila)

            if custo_atual > distancias[atual]:
                continue

            for vizinho, custo_enlace in grafo.get(atual, {}).items():

                novo_custo = custo_atual + custo_enlace

                # Só atualiza quando encontramos um caminho melhor.
                if (
                    vizinho not in distancias
                    or novo_custo < distancias[vizinho]
                ):
                    distancias[vizinho] = novo_custo

                    # Se estamos saindo da origem, o vizinho é
                    # diretamente o próximo salto.
                    if atual == origem:
                        proximos_saltos[vizinho] = vizinho
                    else:
                        # Nos demais casos, preservamos o primeiro
                        # salto do caminho já encontrado.
                        proximos_saltos[vizinho] = (
                            proximos_saltos[atual]
                        )

                    heapq.heappush(
                        fila,
                        (novo_custo, vizinho)
                    )

        # distancias: menor custo até cada destino.
        # proximos_saltos: primeiro roteador do caminho até cada destino.
        return distancias, proximos_saltos

    def obter_rota(
        self,
        destino: str
    ) -> EntradaRota | None:
        return self.tabela.get(destino)

    def obter_todas_rotas(self) -> list[EntradaRota]:
        return list(self.tabela.values())
