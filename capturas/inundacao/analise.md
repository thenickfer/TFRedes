  ## Inundação (Queda de R5 — 10.5.5.1)
  
  ### 1. Identificação das ondas de LSP causadas pela queda
  
  Como R5 (10.5.5.1, porta 6004) possuía dois vizinhos diretos (R4 na porta 6003 e R3 na porta 6002), ambos detectaram a falta de HELLO após o
  timeout de 20 s com uma diferença de ~165 ms entre si, gerando duas ondas de inundação:


  #### Onda 1 — LSP gerado por R4 (10.5.4.1), seq = 1795451128 (t = 21,785 s a 21,792 s)
  
  Payload: LSP:10.5.4.1:1795451128:10.5.2.1=4;10.5.3.1=2 (já sem 10.5.5.1)
  
| Frame | Origem → Destino | Resultado |
| -- | --- | ---- |
|    81  | R4 (6003) → R2 (6001)            | Aceito por R2 (atualiza LSDB e reenvia para R1 e R3) |
|    82   | R4 (6003) → R3 (6002)            | Aceito por R3 (atualiza LSDB e reenvia para R1, R2 e R5)|
|    83                | R2 (6001) → R1 (6000)            | Aceito por R1 (atualiza LSDB e reenvia para R3)|
|    84                | R3 (6002) → R1 (6000)            | Descartado como cópia por R1 (já recebeu no frame 83)|
|    85                | R2 (6001) → R3 (6002)            | Descartado como cópia por R3 (já recebeu no frame 82)|
|    86                | R3 (6002) → R2 (6001)            | Descartado como cópia por R2 (já recebeu no frame 81)|
|    87                | R3 (6002) → R5 (6004)            | Não entregue (R5 já estava offline; R3 ainda não havia dado timeout) |
|    89                | R1 (6000) → R3 (6002)            | Descartado como cópia por R3 (já recebeu no frame 82)|

8 pacotes LSP circularam → 3 aceitos, 4 descartados como cópias, 1 perdido/não entregue (para R5 offline).

 #### Onda 2 — LSP gerado por R3 (10.5.3.1), seq = 1795451122 (t = 21,950 s a 21,955 s)
  
  Payload: LSP:10.5.3.1:1795451122:10.5.1.1=5;10.5.2.1=1;10.5.4.1=2 (já sem 10.5.5.1)
  
|Frame               | Origem → Destino                  | Resultado
| -- | --- | ---- |
|90                 | R3 (6002) → R1 (6000)             | Aceito por R1 (atualiza LSDB e reenvia para R2)|
|91                 | R3 (6002) → R2 (6001)             | Aceito por R2 (atualiza LSDB e reenvia para R1 e R4)|
|92                 | R3 (6002) → R4 (6003)             | Aceito por R4 (confirmado em logs_r4.log linha 4; reenvia para R2)|
|93                 | R2 (6001) → R1 (6000)             | Descartado como cópia por R1|
|94                 | R2 (6001) → R4 (6003)             | Descartado como cópia por R4|
|95                 | R1 (6000) → R2 (6001)             | Descartado como cópia por R2|
|96                 | R4 (6003) → R2 (6001)             | Descartado como cópia por R2|

7 pacotes LSP circularam → 3 aceitos, 4 descartados como cópias.

 ### 2. Contagem consolidada
  
  • Total de pacotes UDP LSP que circularam pela queda de R5: 15 pacotes (8 da onda de R4 + 7 da onda de R3). 
  • Total aceitos (que atualizaram a LSDB): 6 pacotes (3 em cada onda — exatamente 1 por roteador remoto ativo). 
  • Total descartados como cópias: 8 pacotes (4 em cada onda), mais 1 pacote enviado ao nó já caído (frame 87).
  
### 3. Análise e comparação com Vetor de Distância (DV)
  
Ocorreram 8 cópias descartadas pois sempre que um roteador recebe um LSP novo, ele o repassa pra todos vizinhos ativos, exceto sua origem. Como a topologia tem diversos ciclos, dois vizinhos podem reenviar um LSP já recebido pelo outro. O número de sequência mostra que a cópia pode ou não ser descartada, parando a inundação naquele sentido.

Já em um vetor de distância, roteadores trocam vetores apenas com seus vizinhos diretos. Na queda de R5, R4 acreditaria que ainda alcança R5 por R3, e essa rota falsa se propagaria pela rede, gerando o problema de contagem ao infinito (nesse caso, nem split-horizon e poison reverse iriam adiantar), incrementando o custo da rota para R5 até atingir o limite, consumindo muito mais pacotes e tempo até convergir.

Conclusão: O Link-State gera sobrecarga de cópias redundantes durante a inundação (8 cópias em 15 pacotes neste experimento), mas
      garante convergência rápida em uma única rodada (~7 ms por onda, ~170 ms no total entre as duas detecções) e é imune à contagem ao
      infinito.