
from dataclasses import dataclass

from tfredes.pacotes import PacLSP

@dataclass
class EstadoVizinho: #estado de um vizinho
    endereco_virtual: str
    ip: str #fisico
    porta: int
    custo: int

    ativo: bool = False

    ultimo_hello: float = 0.0 


@dataclass
class EntradaLSDB: #registro do lsdb
    lsp: PacLSP
    ultimo_recebimento: float # Momento em que o LSP mais recente foi recebido


@dataclass
class EntradaRota: #criado depois do dijkstra
    rede_destino: str
    proximo_salto: str #end virtual
    custo: int


@dataclass
class PingPendente:
    id: int #solicitacao que originou
    destino: str
    horario_envio: float #para calcular RTT
