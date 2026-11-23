from abc import ABC
from dataclasses import dataclass, field
from enum import IntEnum
from ipaddress import IPv4Address

TAMANHO_MAX_PACOTE = 4096


def eh_ipv4_valido(endereco: str) -> bool:
    if not endereco:
        return False
    try:
        return str(IPv4Address(endereco)) == endereco
    except ValueError:
        return False


def _parse_int(texto: str, minimo: int = 0) -> int | None:
    if not texto or not texto.isdigit():
        return None
    valor = int(texto)
    if valor < minimo:
        return None
    return valor


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
        viz_str = ";".join(f"{v}={c}" for v, c in pacote.vizinhos.items())
        texto = f"LSP:{pacote.origem}:{pacote.sequencia}:{viz_str}"
    elif isinstance(pacote, PacDados):
        if not pacote.mensagem or ":" in pacote.mensagem:
            raise ValueError("Mensagem de dados vazia ou contendo ':'.")
        if not pacote.mensagem.isascii():
            raise ValueError("Mensagem de dados deve conter apenas caracteres ASCII.")
        texto = f"DADOS:{pacote.origem}:{pacote.destino}:{pacote.ttl}:{pacote.id}:{pacote.mensagem}"
    elif isinstance(pacote, PacICMP):
        texto = f"ICMP:{pacote.origem}:{pacote.destino}:{pacote.ttl}:{pacote.id}:{int(pacote.tipo)}"
    else:
        raise ValueError(f"Tipo de pacote desconhecido: {type(pacote)}")
    return texto.encode("ascii")


def desserializar_pacote(dados: bytes) -> Pacote | None:
    if not isinstance(dados, (bytes, bytearray)) or not (0 < len(dados) <= TAMANHO_MAX_PACOTE):
        return None
    try:
        texto = dados.decode("ascii")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in texto):
            return None

        partes = texto.split(":")
        tipo = partes[0]

        if tipo == "HELLO":
            if len(partes) != 2:
                return None
            endereco_virtual = partes[1]
            if not eh_ipv4_valido(endereco_virtual):
                return None
            return PacHello(endereco_virtual=endereco_virtual)

        if tipo == "LSP":
            if len(partes) != 4:
                return None
            _, origem, seq_str, viz_str = partes
            if not eh_ipv4_valido(origem):
                return None
            seq = _parse_int(seq_str, minimo=0)
            if seq is None:
                return None
            vizinhos: dict[str, int] = {}
            if viz_str:
                if viz_str.endswith(";") and len(viz_str) > 1:
                    viz_str = viz_str[:-1]
                for item in viz_str.split(";"):
                    if item.count("=") != 1:
                        return None
                    v, c_str = item.split("=", 1)
                    custo = _parse_int(c_str, minimo=1)
                    if not eh_ipv4_valido(v) or custo is None:
                        return None
                    vizinhos[v] = custo
            return PacLSP(origem=origem, sequencia=seq, vizinhos=vizinhos)

        if tipo == "DADOS":
            if len(partes) != 6:
                return None
            _, origem, destino, ttl_str, id_str, msg = partes
            if not eh_ipv4_valido(origem) or not eh_ipv4_valido(destino):
                return None
            ttl = _parse_int(ttl_str, minimo=1)
            id_pac = _parse_int(id_str, minimo=0)
            if ttl is None or id_pac is None or not msg:
                return None
            return PacDados(origem=origem, destino=destino, ttl=ttl, id=id_pac, mensagem=msg)

        if tipo == "ICMP":
            if len(partes) != 6:
                return None
            _, origem, destino, ttl_str, id_str, tipo_str = partes
            if not eh_ipv4_valido(origem) or not eh_ipv4_valido(destino):
                return None
            ttl = _parse_int(ttl_str, minimo=1)
            id_pac = _parse_int(id_str, minimo=0)
            tipo_int = _parse_int(tipo_str, minimo=0)
            if ttl is None or id_pac is None or tipo_int is None:
                return None
            return PacICMP(
                origem=origem,
                destino=destino,
                ttl=ttl,
                id=id_pac,
                tipo=TipoICMP(tipo_int),
            )
    except ValueError:
        return None
    return None