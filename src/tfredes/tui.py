from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import DataTable, Footer, Header, Input, RichLog, TabbedContent, TabPane

from tfredes.pacotes import PacDados, PacICMP, TipoICMP, eh_ipv4_valido
from tfredes.trata_pacotes import AcaoEncaminhamento

if TYPE_CHECKING:
    from tfredes.roteador import Roteador


class RoteadorApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #painel-estado {
        height: 11;
        min-height: 9;
        border: round $primary;
    }

    #painel-estado DataTable {
        height: 1fr;
    }

    #area-central {
        height: 1fr;
    }

    #console {
        width: 1fr;
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }

    #painel-logs {
        width: 1fr;
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }

    #entrada-comando {
        dock: bottom;
        margin-top: 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Sair"),
        Binding("ctrl+l", "limpar_console", "Limpar"),
        Binding("f1", "aba_tabela", "Tabela"),
        Binding("f2", "aba_vizinhos", "Vizinhos"),
        Binding("f3", "aba_lsdb", "LSDB"),
    ]

    def __init__(self, roteador: Roteador):
        super().__init__()
        self.roteador = roteador
        self.title = f"TFRedes — Roteador {roteador.config.virtual_ip}"
        self.sub_title = f"UDP :{roteador.config.udp_port}"
        self._historico: list[str] = []
        self._indice_historico: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="painel-estado"):
            with TabPane("Tabela de Roteamento [F1]", id="tab-tabela"):
                yield DataTable(id="dt-tabela", zebra_stripes=True)
            with TabPane("Vizinhos [F2]", id="tab-vizinhos"):
                yield DataTable(id="dt-vizinhos", zebra_stripes=True)
            with TabPane("LSDB [F3]", id="tab-lsdb"):
                yield DataTable(id="dt-lsdb", zebra_stripes=True)
        with Horizontal(id="area-central"):
            console = RichLog(id="console", highlight=True, markup=True, wrap=True)
            console.border_title = "Console & Mensagens"
            yield console

            painel_logs = RichLog(id="painel-logs", highlight=True, markup=False, wrap=True)
            painel_logs.border_title = "Logs em Tempo Real"
            yield painel_logs
        yield Input(
            placeholder="Comandos: tabela | lsdb | vizinhos | msg <destino> <texto> | ping <destino> [TTL] | ajuda | sair",
            id="entrada-comando",
        )
        yield Footer()

    def on_mount(self) -> None:
        dt_tabela = self.query_one("#dt-tabela", DataTable)
        dt_tabela.add_columns("Rede Destino", "Próximo Salto", "Custo")

        dt_vizinhos = self.query_one("#dt-vizinhos", DataTable)
        dt_vizinhos.add_columns("Endereço Virtual", "IP Real", "Porta", "Custo", "Status")

        dt_lsdb = self.query_one("#dt-lsdb", DataTable)
        dt_lsdb.add_columns("Origem", "Sequência", "Vizinhos e Custos")

        self.roteador.on_mensagem_recebida = self._ao_receber_mensagem
        self.roteador.on_estado_alterado = self.atualizar_paineis
        self.roteador.logs.on_log = self._ao_registrar_log

        self.atualizar_paineis()
        self.set_interval(2.0, self.atualizar_paineis)

        console = self.query_one("#console", RichLog)
        console.write(
            f"[bold cyan]Roteador {self.roteador.config.virtual_ip}[/bold cyan] "
            f"iniciado na porta UDP [bold]{self.roteador.config.udp_port}[/bold]."
        )
        self._mostrar_ajuda()
        self.query_one("#entrada-comando", Input).focus()

    def on_unmount(self) -> None:
        self.roteador.on_mensagem_recebida = None
        self.roteador.on_estado_alterado = None
        self.roteador.logs.on_log = None

    def _hora(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _ao_registrar_log(self, linha: str) -> None:
        if not self.is_mounted:
            return
        self.query_one("#painel-logs", RichLog).write(linha)

    def atualizar_paineis(self) -> None:
        if not self.is_mounted:
            return

        dt_tabela = self.query_one("#dt-tabela", DataTable)
        dt_tabela.clear()
        rotas = sorted(
            self.roteador.gerenciador_roteamento.obter_todas_rotas(),
            key=lambda r: r.rede_destino,
        )
        for rota in rotas:
            dt_tabela.add_row(rota.rede_destino, rota.proximo_salto, str(rota.custo))

        dt_vizinhos = self.query_one("#dt-vizinhos", DataTable)
        dt_vizinhos.clear()
        vizinhos = sorted(
            self.roteador.gerenciador_vizinhos.vizinhos.values(),
            key=lambda v: v.endereco_virtual,
        )
        for viz in vizinhos:
            status = Text("ATIVO", style="bold green") if viz.ativo else Text("INATIVO", style="dim red")
            dt_vizinhos.add_row(
                viz.endereco_virtual,
                viz.ip,
                str(viz.porta),
                str(viz.custo),
                status,
            )

        dt_lsdb = self.query_one("#dt-lsdb", DataTable)
        dt_lsdb.clear()
        lsps = sorted(
            self.roteador.gerenciador_lsdb.obter_todos_lsps(),
            key=lambda lsp: lsp.origem,
        )
        for lsp in lsps:
            viz_str = ";".join(
                f"{v}={c}" for v, c in sorted(lsp.vizinhos.items())
            ) or "(sem vizinhos ativos)"
            dt_lsdb.add_row(lsp.origem, str(lsp.sequencia), viz_str)

    def _ao_receber_mensagem(self, pacote: PacDados) -> None:
        if not self.is_mounted:
            return
        console = self.query_one("#console", RichLog)
        console.write(
            f"[dim]{self._hora()}[/dim] [bold green]MSG RECEBIDA[/bold green] "
            f"de [bold]{pacote.origem}[/bold] (para {pacote.destino}, TTL={pacote.ttl}): "
            f"{pacote.mensagem}"
        )

    def action_limpar_console(self) -> None:
        self.query_one("#console", RichLog).clear()

    def action_aba_tabela(self) -> None:
        self.query_one("#painel-estado", TabbedContent).active = "tab-tabela"

    def action_aba_vizinhos(self) -> None:
        self.query_one("#painel-estado", TabbedContent).active = "tab-vizinhos"

    def action_aba_lsdb(self) -> None:
        self.query_one("#painel-estado", TabbedContent).active = "tab-lsdb"

    def on_key(self, event: Key) -> None:
        entrada = self.query_one("#entrada-comando", Input)
        if not entrada.has_focus or not self._historico:
            return

        if event.key == "up":
            if self._indice_historico > 0:
                self._indice_historico -= 1
            entrada.value = self._historico[self._indice_historico]
            entrada.cursor_position = len(entrada.value)
            event.prevent_default()
        elif event.key == "down":
            if self._indice_historico < len(self._historico) - 1:
                self._indice_historico += 1
                entrada.value = self._historico[self._indice_historico]
            else:
                self._indice_historico = len(self._historico)
                entrada.value = ""
            entrada.cursor_position = len(entrada.value)
            event.prevent_default()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        linha = event.value.strip()
        event.input.value = ""
        if not linha:
            return

        if not self._historico or self._historico[-1] != linha:
            self._historico.append(linha)
        self._indice_historico = len(self._historico)

        console = self.query_one("#console", RichLog)
        console.write(f"[dim]{self._hora()}[/dim] [bold cyan]>[/bold cyan] {linha}")

        partes = linha.split(maxsplit=2)
        cmd = partes[0].lower()

        if cmd == "tabela":
            self.action_aba_tabela()
            self._cmd_tabela()
        elif cmd == "lsdb":
            self.action_aba_lsdb()
            self._cmd_lsdb()
        elif cmd == "vizinhos":
            self.action_aba_vizinhos()
            self._cmd_vizinhos()
        elif cmd == "msg":
            if len(partes) < 3:
                console.write("[yellow]Uso: msg <destino> <texto>[/yellow]")
            else:
                self._cmd_msg(partes[1], partes[2])
        elif cmd == "ping":
            args_ping = linha.split()
            if len(args_ping) < 2 or len(args_ping) > 3:
                console.write("[yellow]Uso: ping <destino> [TTL][/yellow]")
            else:
                destino = args_ping[1]
                if not eh_ipv4_valido(destino):
                    console.write(f"[red]Endereço de destino inválido:[/red] {destino}")
                    return
                ttl = 16
                if len(args_ping) == 3:
                    try:
                        ttl = int(args_ping[2])
                        if ttl <= 0:
                            raise ValueError
                    except ValueError:
                        console.write("[red]TTL inválido: informe um inteiro positivo.[/red]")
                        return
                self.run_worker(self._cmd_ping(destino, ttl), exclusive=False)
        elif cmd in ("limpar", "clear"):
            self.action_limpar_console()
        elif cmd in ("ajuda", "help"):
            self._mostrar_ajuda()
        elif cmd in ("sair", "quit", "exit"):
            self.exit()
        else:
            console.write(f"[red]Comando desconhecido:[/red] {cmd}. Digite [bold]ajuda[/bold].")

    def _mostrar_ajuda(self) -> None:
        console = self.query_one("#console", RichLog)
        tabela = Table(title="Comandos Disponíveis", show_header=True, header_style="bold cyan")
        tabela.add_column("Comando", style="bold")
        tabela.add_column("Ação")
        tabela.add_row("tabela", "Exibe a tabela de roteamento (rede, próximo salto, custo)")
        tabela.add_row("lsdb", "Exibe a LSDB (origem, sequência, vizinhos e custos)")
        tabela.add_row("vizinhos", "Exibe os vizinhos ativos (endereço virtual, IP real e porta)")
        tabela.add_row("msg <destino> <texto>", "Envia um pacote de dados (ASCII, sem ':')")
        tabela.add_row("ping <destino> [TTL]", "Envia pedido de eco (TTL padrão: 16, timeout: 2s)")
        tabela.add_row("limpar / sair", "Limpa o console / encerra o roteador")
        console.write(tabela)

    def _cmd_tabela(self) -> None:
        console = self.query_one("#console", RichLog)
        rotas = sorted(
            self.roteador.gerenciador_roteamento.obter_todas_rotas(),
            key=lambda r: r.rede_destino,
        )
        if not rotas:
            console.write("[yellow]Tabela de roteamento vazia (nenhum destino alcançável).[/yellow]")
            return

        tabela = Table(title="Tabela de Roteamento", header_style="bold cyan")
        tabela.add_column("Rede Destino")
        tabela.add_column("Próximo Salto")
        tabela.add_column("Custo", justify="right")
        for rota in rotas:
            tabela.add_row(rota.rede_destino, rota.proximo_salto, str(rota.custo))
        console.write(tabela)

    def _cmd_lsdb(self) -> None:
        console = self.query_one("#console", RichLog)
        lsps = sorted(
            self.roteador.gerenciador_lsdb.obter_todos_lsps(),
            key=lambda lsp: lsp.origem,
        )
        if not lsps:
            console.write("[yellow]LSDB vazia.[/yellow]")
            return

        tabela = Table(title="LSDB", header_style="bold cyan")
        tabela.add_column("Origem")
        tabela.add_column("Sequência", justify="right")
        tabela.add_column("Vizinhos e Custos")
        for lsp in lsps:
            viz_str = ";".join(
                f"{v}={c}" for v, c in sorted(lsp.vizinhos.items())
            ) or "(nenhum)"
            tabela.add_row(lsp.origem, str(lsp.sequencia), viz_str)
        console.write(tabela)

    def _cmd_vizinhos(self) -> None:
        console = self.query_one("#console", RichLog)
        ativos = sorted(
            self.roteador.gerenciador_vizinhos.obter_vizinhos_ativos(),
            key=lambda v: v.endereco_virtual,
        )
        if not ativos:
            console.write("[yellow]Nenhum vizinho ativo no momento.[/yellow]")
            return

        tabela = Table(title="Vizinhos Ativos", header_style="bold green")
        tabela.add_column("Endereço Virtual")
        tabela.add_column("IP Real")
        tabela.add_column("Porta", justify="right")
        for viz in ativos:
            tabela.add_row(viz.endereco_virtual, viz.ip, str(viz.porta))
        console.write(tabela)

    def _cmd_msg(self, destino: str, texto: str) -> None:
        console = self.query_one("#console", RichLog)
        if not eh_ipv4_valido(destino):
            console.write(f"[red]Endereço de destino inválido:[/red] {destino}")
            return
        if ":" in texto:
            console.write("[red]Mensagem inválida:[/red] o texto não pode conter o caractere ':'.")
            return
        if not texto.isascii():
            console.write("[red]Mensagem inválida:[/red] o texto deve conter apenas caracteres ASCII.")
            return

        res = self.roteador.enviar_dados(destino, texto)

        if res.acao == AcaoEncaminhamento.ENCAMINHAR:
            console.write(
                f"[green]Mensagem enviada[/green] para [bold]{destino}[/bold] "
                f"(próximo salto: {res.proximo_salto})."
            )
        elif res.acao == AcaoEncaminhamento.ENTREGA_DADOS:
            console.write(f"[green]Mensagem entregue localmente[/green] para [bold]{destino}[/bold].")
        elif res.acao == AcaoEncaminhamento.DESTINO_INALCANCAVEL:
            console.write(f"[red]Destino inalcançável:[/red] {res.observacoes}")
        else:
            console.write(f"[red]Falha ao enviar mensagem:[/red] {res.observacoes or res.acao.value}")

    async def _cmd_ping(self, destino: str, ttl: int) -> None:
        console = self.query_one("#console", RichLog)
        console.write(f"[dim]Enviando ping para {destino} (TTL={ttl})...[/dim]")

        resultado = await self.roteador.enviar_ping(destino, ttl=ttl, timeout=2.0)
        status = resultado["status"]

        if status == "sem_rota":
            console.write(f"[red]PING {destino}:[/red] {resultado['observacoes']}")
            return

        if status == "timeout":
            console.write(f"[yellow]PING {destino} (TTL={ttl}):[/yellow] Timeout (sem resposta após 2s).")
            return

        pacote: PacICMP = resultado["pacote"]
        rtt_ms: float = resultado["rtt_ms"]
        tipo = TipoICMP(int(pacote.tipo))

        if tipo == TipoICMP.ECHO_REPLY:
            console.write(
                f"[bold green]ECHO REPLY[/bold green] de [bold]{pacote.origem}[/bold]: "
                f"id={pacote.id} ttl={pacote.ttl} RTT=[bold]{rtt_ms:.2f} ms[/bold]"
            )
        elif tipo == TipoICMP.TEMPO_EXCEDIDO:
            console.write(
                f"[bold yellow]TEMPO EXCEDIDO[/bold yellow] reportado por [bold]{pacote.origem}[/bold]: "
                f"id={pacote.id} RTT=[bold]{rtt_ms:.2f} ms[/bold]"
            )
        elif tipo == TipoICMP.DESTINO_INACESSIVEL:
            console.write(
                f"[bold red]DESTINO INACESSÍVEL[/bold red] reportado por [bold]{pacote.origem}[/bold]: "
                f"id={pacote.id} RTT=[bold]{rtt_ms:.2f} ms[/bold]"
            )
        else:
            console.write(
                f"[cyan]ICMP tipo {int(tipo)}[/cyan] de [bold]{pacote.origem}[/bold]: "
                f"id={pacote.id} RTT=[bold]{rtt_ms:.2f} ms[/bold]"
            )
