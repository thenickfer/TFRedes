# TFRedes — Simulador de Roteamento Link-State

Simulador de roteadores IPv4 sobre UDP com descoberta de vizinhança (`HELLO`), inundação de estado de enlace (`LSP` / `LSDB`), cálculo de caminhos mínimos via algoritmo de **Dijkstra**, encaminhamento de pacotes de dados e mensagens de controle **ICMP** (`Echo Request`, `Echo Reply`, `Tempo Excedido` e `Destino Inacessível`), e interface interativa de terminal (**Textual TUI**) com logs em tempo real.

---

## Topologia de Teste (5 Roteadores)

![Topologia de Teste](topologia.png)

Os arquivos da topologia de teste encontram-se em `src/roteadores/r1/r1.yaml` a `r5.yaml`.

---

## Requisitos e Instalação

O projeto utiliza Python `>= 3.14` e [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

---

## Como Executar

Obs.: Se quiser, eu gosto de [rodar pelo docker](#docker-compose)

Você pode iniciar qualquer roteador informando apenas o **número do roteador** (`1` a `5`), o nome curto (`r1` a `r5`) ou o **caminho completo** para um arquivo YAML de configuração:

```bash
# Pelo número do roteador (procura em src/roteadores/r1/r<N>.yaml)
uv run tfredes 1
uv run tfredes 2
uv run tfredes 3
uv run tfredes 4
uv run tfredes 5

# Ou passando o caminho explícito de um arquivo YAML
uv run tfredes src/roteadores/r1/r1.yaml
```

Cada instância abre uma interface de terminal única contendo:
- **Abas superiores (`F1`, `F2`, `F3`)**: Tabela de Roteamento, Vizinhos e LSDB atualizados automaticamente.
- **Painel central esquerdo**: Console interativo de comandos e mensagens recebidas.
- **Painel central direito**: Logs de eventos do roteador em tempo real (além de persistidos em `<roteador>.log`).
- **Barra inferior**: Entrada de comandos com histórico nas setas `↑`/`↓`.

---

## Formato do Arquivo de Configuração (YAML)

Cada roteador é configurado por um arquivo YAML com os seguintes campos:

```yaml
virtual_ip: "10.5.1.1"   # (Obrigatório) Endereço IPv4 virtual do roteador (responsável pela rede 10.5.1.0/24)
udp_port: 6000           # (Opcional) Porta UDP local para envio e recebimento (padrão: 6000, intervalo: 1..65535)

neighbors:               # Mapa de vizinhos diretos configurados
  10.5.2.1:              # Endereço IPv4 virtual do vizinho
    ip: "127.0.0.1"      # (Obrigatório) Endereço IPv4 real (físico) do vizinho
    port: 6001           # (Obrigatório) Porta UDP do vizinho (1..65535)
    cost: 2              # (Obrigatório) Custo do enlace (inteiro estritamente positivo, > 0)

  10.5.3.1:
    ip: "127.0.0.1"
    port: 6002
    cost: 5
```

### Regras de Validação da Configuração
- `virtual_ip` e `neighbors.<viz>.ip` devem ser strings com endereços IPv4 válidos.
- `udp_port` e `neighbors.<viz>.port` devem ser inteiros entre `1` e `65535` (`udp_port` assume `6000` quando omitido).
- `neighbors.<viz>.cost` deve ser um **inteiro positivo (`> 0`)**; valores `<= 0`, booleanos ou não numéricos são rejeitados na inicialização.

---

## Comandos da Interface

| Comando | Ação |
| :--- | :--- |
| `tabela` | Exibe a tabela de roteamento (rede de destino, próximo salto e custo total). |
| `lsdb` | Exibe a Link-State Database (origem, número de sequência, vizinhos ativos e custos). |
| `vizinhos` | Exibe os vizinhos ativos (endereço virtual, IP real e porta UDP). |
| `msg <destino> <texto>` | Envia um pacote `DADOS` ao endereço virtual `<destino>` (texto ASCII sem `:`). |
| `ping <destino> [TTL]` | Envia um `ICMP Echo Request` (tipo 8) com o TTL indicado (padrão: `16`) e exibe a resposta (`Echo Reply`, `Tempo Excedido` ou `Destino Inacessível`), quem respondeu e o RTT, ou timeout após `2 s`. |
| `limpar` / `Ctrl+L` | Limpa o console de comandos. |
| `sair` / `Ctrl+Q` | Encerra o roteador de forma limpa. |


## Docker Compose

também é possível rodar pelo docker compose, a vantagem é que os containers usam uma subrede dentro do compose, cada um com seu próprio IP
primeiro, build na imagem:
```
docker build -t roteadortf:latest .
```

depois só rodar:
```
docker compose up -d
docker compose attach <routerN>
```
