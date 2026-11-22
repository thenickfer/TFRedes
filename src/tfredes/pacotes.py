from abc import ABC
from dataclasses import dataclass, field
from enum import IntEnum


class TipoICMP(IntEnum):
    ECHO_REPLY = 0
    DESTINO_INACESSIVEL = 3
    ECHO_REQUEST = 8
    TEMPO_EXCEDIDO = 11


#pacote base
class Pacote(ABC):
    pass


#Quando for desserializar vai virar um desses com base 
#no primeiro parametro antes dos ":"

@dataclass
class PacHello(Pacote):
    endereco_virtual: str  # vai string mesmo pra nao ter que criar objeto endereco ex: '10.5.1.1'


@dataclass
class PacLSP(Pacote):
    origem: str
    sequencia: int
    # dicionario mapeia vizinho -> custo
    vizinhos: dict[str, int] = field(default_factory=dict)


#para Dados e ICMP
@dataclass
class PacRoteavel(Pacote, ABC):
    origem: str
    destino: str
    ttl: int
    id: int

    def ttl_update_check(self) -> bool: #acho q da pra fazer os dois aqui
        self.ttl -= 1
        return self.ttl > 0 


@dataclass
class PacDados(PacRoteavel):
    mensagem: str


@dataclass
class PacICMP(PacRoteavel):
    tipo: TipoICMP | int