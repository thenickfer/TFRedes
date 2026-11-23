
from dataclasses import dataclass
from enum import Enum

from pacotes import Pacote, PacDados, PacICMP, PacRoteavel, TipoICMP
from roteamento import GerenciadorRoteamento
from logs import Logs


class AcaoEncaminhamento(Enum):
    ENCAMINHAR = "encaminhar"
    ENTREGA_DADOS = "entrega_dados"
    RESULTADO_ICMP = "resultado_icmp"
    RESPOSTA_ECO = "resposta_eco"
    ICMP_GERADO = "icmp_gerado"
    DESTINO_INALCANCAVEL = "destino_inalcancavel"
    DESCARTAR = "descartar"


@dataclass
class ResultadoEncaminhamento:
    acao: AcaoEncaminhamento #oque foi decidido

    pacote: Pacote | None = None

    proximo_salto: str | None = None #end virtual

    observacoes: str = ""


class Encaminhador:
    def __init__(
        self,
        endereco_virtual: str,
        roteamento: GerenciadorRoteamento,
        logs: Logs
    ):
        self.endereco_virtual = endereco_virtual
        self.roteamento = roteamento
        self.logs = logs

    def _mesma_rede(self, destino: str) -> bool:
        #presume-se que todas as redes sao /24

        partes_origem = self.endereco_virtual.split(".")
        partes_destino = destino.split(".")

        if len(partes_origem) != 4 or len(partes_destino) != 4:
            return False

        return partes_origem[:3] == partes_destino[:3]

    def _roteador_da_rede(self, destino: str) -> str | None:
        #Converte o endereço de destino para o endereço virtual
        #do roteador que representa sua rede
        #ex: 10.5.3.50 -> 10.5.3.1
        partes = destino.split(".")

        if len(partes) != 4: #acho que valida quando for des/serializar
            return None

        return ".".join(partes[:3]) + ".1"

    def _gerar_icmp_erro(
        self,
        pacote: PacRoteavel,
        tipo: TipoICMP
    ) -> ResultadoEncaminhamento:
        #gera uma mensagem ICMP de erro para a origem
        #do pacote que criar problema

        if isinstance(pacote, PacICMP):
            if int(pacote.tipo) in (
                TipoICMP.TEMPO_EXCEDIDO,
                TipoICMP.DESTINO_INACESSIVEL
            ):
                return ResultadoEncaminhamento(
                    acao = AcaoEncaminhamento.DESCARTAR,
                    observacoes = "Erro icmp"
                )

        erro = PacICMP(
            origem = self.endereco_virtual,
            destino = pacote.origem,
            ttl = 16,
            id = pacote.id,
            tipo = tipo
        )

        self.logs.criaLog(
            "ICMP",
            f"Mensagem ICMP tipo {int(tipo)} gerada "
            f"para {pacote.origem}."
        )

        return ResultadoEncaminhamento(
            acao=AcaoEncaminhamento.ICMP_GERADO,
            pacote=erro
        )

    def _entregar_localmente(
        self,
        pacote: PacRoteavel
    ) -> ResultadoEncaminhamento:
        #nao existem hosts reais

        if isinstance(pacote, PacDados):
            return ResultadoEncaminhamento(
                acao=AcaoEncaminhamento.ENTREGA_DADOS,
                pacote=pacote
            )

        if isinstance(pacote, PacICMP):

            # eco: cria uma resposta com o mesmo id
            if int(pacote.tipo) == TipoICMP.ECHO_REQUEST:
                resposta = PacICMP(
                    origem=pacote.destino,
                    destino=pacote.origem,
                    ttl=16,
                    id=pacote.id,
                    tipo=TipoICMP.ECHO_REPLY
                )

                return ResultadoEncaminhamento(
                    acao=AcaoEncaminhamento.RESPOSTA_ECO,
                    pacote=resposta
                )

            # resposta de eco ou mensagem de erro:
            # a interface deverá exibir o resultado.
            return ResultadoEncaminhamento(
                acao=AcaoEncaminhamento.RESULTADO_ICMP,
                pacote=pacote
            )

        return ResultadoEncaminhamento(
            acao=AcaoEncaminhamento.DESCARTAR,
            observacoes="Tipo de pacote invalido"
        )

    def preparar_pacote_originado(
        self,
        pacote: PacRoteavel
    ) -> ResultadoEncaminhamento:
        #Prepara um pacote criado pelo proprio roteador
        #ttl permanece inalterado neste roteador

        #hosts reais nao existem
        if self._mesma_rede(pacote.destino):
            return self._entregar_localmente(pacote)

        return self._consultar_rota(pacote, recebido=False)

    def processar_pacote_recebido(
        self,
        pacote: PacRoteavel
    ) -> ResultadoEncaminhamento:

        # Primeiro verificamos se o destino pertence à rede local.
        # Nesse caso, o TTL não precisa ser decrementado.
        if self._mesma_rede(pacote.destino):
            return self._entregar_localmente(pacote)

        # Pacotes destinados a outras redes precisam ter o TTL
        # decrementado antes de serem encaminhados.
        if not pacote.ttl_update_check():

            return self._gerar_icmp_erro(
                pacote,
                TipoICMP.TEMPO_EXCEDIDO
            )

        return self._consultar_rota(pacote, recebido=True)

    def _consultar_rota(
        self,
        pacote: PacRoteavel,
        recebido: bool
    ) -> ResultadoEncaminhamento:
        #consulta se pode ser entregue conforme tabela

        destino_rede = self._roteador_da_rede(pacote.destino)

        if destino_rede is None:
            return ResultadoEncaminhamento(
                acao=AcaoEncaminhamento.DESCARTAR,
                observacoes="Destino invalido."
            )

        rota = self.roteamento.obter_rota(destino_rede)

        if rota is None:

            # se for local so informa que nao ha rota
            if not recebido:
                return ResultadoEncaminhamento(
                    acao=AcaoEncaminhamento.DESTINO_INALCANCAVEL,
                    observacoes=f"Não existe rota para {pacote.destino}."
                )

            # se for recebido emite icmp
            return self._gerar_icmp_erro(
                pacote,
                TipoICMP.DESTINO_INACESSIVEL
            )

        self.logs.criaLog(
            "ENCAMINHAMENTO",
            f"Pacote destinado a {pacote.destino}: "
            f"próximo salto {rota.proximo_salto}, TTL {pacote.ttl}."
        )

        return ResultadoEncaminhamento(
            acao=AcaoEncaminhamento.ENCAMINHAR,
            pacote=pacote,
            proximo_salto=rota.proximo_salto
        )