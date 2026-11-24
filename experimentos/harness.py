"""Experimentos do relatorio: roda as 5 instancias do roteador (sem a TUI) e injeta falhas.

Nao altera o codigo do roteador: so troca a interface por comandos roteirizados e,
quando pedido, descarta pacotes na entrada de um roteador (queda de enlace / perda de LSP).

Uso, na raiz do repositorio (portas 6000-6004 livres; leva cerca de 3 minutos):
    uv run python experimentos/harness.py src experimentos > experimentos/saida.txt
Os logs de cada roteador vao para experimentos/r*.log.
"""
import sys, asyncio, time
SRC = sys.argv[1]; OUT = sys.argv[2]
sys.path.insert(0, SRC)
from config.config import load_config
from tfredes.roteador import Roteador
from tfredes.logs import Logs
from tfredes.pacotes import desserializar_pacote, PacLSP, TipoICMP

T0 = time.monotonic()
def ts(): return f"[t={time.monotonic()-T0:7.2f}s]"
def out(*a): print(*a, flush=True)
R = {}
drop_rules = []   # funcoes (n, pacote, endereco) -> motivo|None

def make_filter(n, r):
    orig = r.processar_pacote
    def filt(dados, endereco):
        pac = desserializar_pacote(dados)
        for rule in drop_rules:
            motivo = rule(n, pac, endereco)
            if motivo:
                r.logs.criaLog("FALHA-INJETADA", f"Pacote descartado ({motivo}): {dados.decode('ascii','replace')}")
                return
        orig(dados, endereco)
    r.processar_pacote = filt

async def start(n, cfgpath=None, seq0=None, tag=""):
    cfg = load_config(cfgpath or f"{SRC}/roteadores/r1/r{n}.yaml")
    r = Roteador(cfg, Logs(caminho_arquivo=f"{OUT}/r{n}{tag}.log"))
    if seq0 is not None: r.sequencia_lsp = seq0
    ev = asyncio.Event()
    async def ui(): await ev.wait()
    r.interface_usuario = ui
    make_filter(n, r)
    t = asyncio.create_task(r.run())
    R[n] = (r, ev, t)
    await asyncio.sleep(0)

async def stop(n):
    r, ev, t = R.pop(n); ev.set(); await t

def porta(n): return 6000 + n - 1

def tabela(n):
    r = R[n][0]; out(f"{ts()} R{n} > tabela")
    out(f"  {'Rede Destino':<14}{'Próximo Salto':<15}{'Custo':>5}")
    for e in sorted(r.gerenciador_roteamento.obter_todas_rotas(), key=lambda e: e.rede_destino):
        out(f"  {e.rede_destino:<14}{e.proximo_salto:<15}{e.custo:>5}")
def lsdb(n):
    r = R[n][0]; out(f"{ts()} R{n} > lsdb")
    out(f"  {'Origem':<11}{'Sequência':>11}  Vizinhos e Custos")
    for l in sorted(r.gerenciador_lsdb.obter_todos_lsps(), key=lambda l: l.origem):
        v = ";".join(f"{a}={c}" for a, c in sorted(l.vizinhos.items())) or "(nenhum)"
        out(f"  {l.origem:<11}{l.sequencia:>11}  {v}")
def vizinhos(n):
    r = R[n][0]; out(f"{ts()} R{n} > vizinhos")
    for v in sorted(r.gerenciador_vizinhos.obter_vizinhos_ativos(), key=lambda v: v.endereco_virtual):
        out(f"  {v.endereco_virtual:<11}{v.ip:<11}{v.porta}")
async def ping(n, dest, ttl=16):
    r = R[n][0]
    res = await r.enviar_ping(dest, ttl=ttl)
    s = res["status"]
    if s == "resposta":
        p = res["pacote"]; nome = {0:"ECHO REPLY",11:"TEMPO EXCEDIDO",3:"DESTINO INACESSIVEL"}[int(p.tipo)]
        out(f"{ts()} R{n} > ping {dest} {ttl}  ->  {nome} de {p.origem}: id={p.id} ttl={p.ttl} RTT={res['rtt_ms']:.2f} ms")
    elif s == "sem_rota":
        out(f"{ts()} R{n} > ping {dest} {ttl}  ->  sem rota: {res['observacoes']}")
    else:
        out(f"{ts()} R{n} > ping {dest} {ttl}  ->  timeout (2 s)")
def msg(n, dest, texto):
    res = R[n][0].enviar_dados(dest, texto)
    out(f"{ts()} R{n} > msg {dest} {texto}  ->  {res.acao.value} (proximo salto {res.proximo_salto})")

async def wait_until(cond, limite, passo=0.05):
    ini = time.monotonic()
    while time.monotonic() - ini < limite:
        if cond(): return time.monotonic() - ini
        await asyncio.sleep(passo)
    return None

async def main():
    out("=== E0: subida da rede (R1..R5) ===")
    for n in range(1, 6): await start(n)
    await asyncio.sleep(12)
    vizinhos(1); lsdb(1); tabela(1)
    for n in range(2, 6): tabela(n)

    out("\n=== E1: ping com TTL crescente R1 -> 10.5.5.1, msg, ping para rede inexistente ===")
    for ttl in (1, 2, 3, 4): await ping(1, "10.5.5.1", ttl)
    await ping(1, "10.5.5.1"); await ping(1, "10.5.5.50")
    msg(1, "10.5.5.1", "Oi pessoal"); await asyncio.sleep(0.3)
    await ping(1, "10.5.9.1")

    out("\n=== E2: falha do enlace R3-R4 + perda de TODAS as copias do novo LSP de R3 em R2 ===")
    def enlace34(n, pac, end):
        if (n == 3 and end[1] == porta(4)) or (n == 4 and end[1] == porta(3)): return "enlace R3-R4 caido"
    def perda_lsp_r3_em_r2(n, pac, end):
        if n == 2 and isinstance(pac, PacLSP) and pac.origem == "10.5.3.1": return "perda simulada de LSP de R3 em R2"
    drop_rules.extend([enlace34, perda_lsp_r3_em_r2])
    t_falha = time.monotonic(); out(f"{ts()} falha injetada")
    r3 = R[3][0]
    dt = await wait_until(lambda: "10.5.4.1" not in r3.gerenciador_lsdb.obter_lsp("10.5.3.1").vizinhos, 30)
    out(f"{ts()} R3 detectou a queda do enlace {dt:.2f}s apos a falha")
    await asyncio.sleep(1.5)
    for n in (2, 3): lsdb(n); tabela(n)
    tabela(1)
    await ping(1, "10.5.4.1")
    out(f"{ts()} perda de LSP em R2 encerrada (os proximos LSPs de R3 chegam normalmente)")
    drop_rules.remove(perda_lsp_r3_em_r2); t_fim = time.monotonic()
    r2 = R[2][0]
    dt = await wait_until(lambda: "10.5.4.1" not in r2.gerenciador_lsdb.obter_lsp("10.5.3.1").vizinhos, 35)
    out(f"{ts()} R2 recuperou o LSP atual de R3 {dt:.2f}s depois (renovacao periodica de 30 s)")
    tabela(2); await ping(1, "10.5.4.1")
    drop_rules.remove(enlace34); out(f"{ts()} enlace R3-R4 restaurado")
    await asyncio.sleep(7); tabela(1)

    out("\n=== E3: R4 reinicia numerando LSPs a partir de 0 (e sem o enlace para R5) ===")
    lsdb(1)
    await stop(4); out(f"{ts()} R4 encerrado"); await asyncio.sleep(2)
    await start(4, cfgpath=f"{OUT}/r4_sem_r5.yaml", seq0=0, tag="_seq0")
    out(f"{ts()} R4 reiniciado com sequencia inicial 0 e sem enlace com R5")
    await asyncio.sleep(35)
    lsdb(4); lsdb(1); tabela(1); tabela(3); tabela(4)
    await ping(1, "10.5.5.1")
    r1 = R[1][0]
    dt = await wait_until(lambda: (l := r1.gerenciador_lsdb.obter_lsp("10.5.4.1")) is not None and l.sequencia < 1000, 130, 0.5)
    out(f"{ts()} R1 so aceitou um LSP 'novo' de R4 {dt:.1f}s depois (apos o envelhecimento de 90 s do LSP antigo)")
    lsdb(1); tabela(1); await ping(1, "10.5.5.1")

    out("\n=== E3b (controle): mesmo reinicio, mas com sequencia inicial = Unix time (comportamento do codigo) ===")
    await stop(4); await asyncio.sleep(2)
    await start(4, cfgpath=f"{OUT}/r4_sem_r5.yaml", tag="_unix")
    dt = await wait_until(lambda: r1.gerenciador_lsdb.obter_lsp("10.5.4.1").sequencia > 10**9, 15)
    out(f"{ts()} R1 aceitou o LSP do R4 reiniciado {dt:.2f}s apos o reinicio")
    lsdb(1); tabela(1)
    for n in list(R): await stop(n)

asyncio.run(main())
