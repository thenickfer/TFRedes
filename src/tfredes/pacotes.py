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

def serializar_pacote(pacote: Pacote) -> bytes:
    if isinstance(pacote, PacHello):
        texto = f"HELLO:{pacote.endereco_virtual}"
    elif isinstance(pacote, PacLSP):
        viz_str = ",".join(f"{v}={c}" for v, c in pacote.vizinhos.items())
        texto = f"LSP:{pacote.origem}:{pacote.sequencia}:{viz_str}"
    elif isinstance(pacote, PacDados):
        texto = f"DADOS:{pacote.origem}:{pacote.destino}:{pacote.ttl}:{pacote.id}:{pacote.mensagem}"
    elif isinstance(pacote, PacICMP):
        texto = f"ICMP:{pacote.origem}:{pacote.destino}:{pacote.ttl}:{pacote.id}:{int(pacote.tipo)}"
    else:
        raise ValueError(f"Tipo de pacote desconhecido: {type(pacote)}")
    return texto.encode("utf-8")

def desserializar_pacote(dados: bytes) -> Pacote | None:
    try:
        texto = dados.decode("utf-8").strip()
        tipo, resto = texto.split(":", 1)
        if tipo == "HELLO":
            return PacHello(endereco_virtual=resto)
        if tipo == "LSP":
            origem, seq, viz_str = resto.split(":", 2)
            vizinhos = {}
            if viz_str:
                for item in viz_str.split(","):
                    v, c = item.split("=", 1)
                    vizinhos[v] = int(c)
            return PacLSP(origem=origem, sequencia=int(seq), vizinhos=vizinhos)
        if tipo == "DADOS":
            origem, destino, ttl, id_pac, msg = resto.split(":", 4)
            return PacDados(origem=origem, destino=destino, ttl=int(ttl), id=int(id_pac), mensagem=msg)
        if tipo == "ICMP":
            origem, destino, ttl, id_pac, tipo_icmp = resto.split(":", 4)
            return PacICMP(origem=origem, destino=destino, ttl=int(ttl), id=int(id_pac), tipo=TipoICMP(int(tipo_icmp)))
    except ValueError:
        return None
    return None