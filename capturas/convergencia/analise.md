 ## Resposta — Convergência (Queda de R4 — 10.5.4.1)
  
  ### 1. Cenário e comprovação da mudança de rota (prints de R1)
  
  O roteador R4 (10.5.4.1, porta 6003) estava no caminho mínimo entre R1 (10.5.1.1) e R5 (10.5.5.1):
  
  • Antes da queda (tabelaR1_pre.png, 13:59:23):
      • Rota em R1 para 10.5.5.1: próximo salto 10.5.2.1, custo 6 (R1 → R2 → R3 → R4 → R5).
      • ping 10.5.5.1 (13:59:40): ECHO REPLY com ttl=13 (confirmando 3 roteadores intermediários: R2, R3 e R4) e RTT = 51,85 ms.
  • Depois da queda de R4 (tabelaR1_pos.png, 14:02:51):
      • 10.5.4.1 foi removido da tabela de R1 e a rota para 10.5.5.1 foi recalculada para custo 9 (R1 → R2 → R3 → R5, próximo salto 10.5.2.1).
      • ping 10.5.5.1 (14:02:59): ECHO REPLY com ttl=14 (confirmando que agora há apenas 2 roteadores intermediários: R2 e R3) e RTT = 46,49  
      ms.

 ### 2. Linha do tempo exata (Wireshark — cap_queda_r4.pcapng)                                                                               
                                                                                                                                              
|   Marco                     | Frame | Tempo relativo | Evento
| --- | -- | --- | ---- |
|   t0 (último HELLO de R4)   | 58–60 |   12,7656 s    | Último HELLO:10.5.4.1 enviado por R4 para R2, R3 e R5.|
|   Queda efetiva de R4       | 62–63 |   13,1558 s    | R5 envia HELLO para 6003 e o SO responde ICMP Port Unreachable (R4 já encerrado entre 12,77 s e 13,15 s). |
|   t1 — Detecção em R3       |  142  |   33,2901 s    | R3 dá timeout em R4 e gera LSP:10.5.3.1:1795451175 sem 10.5.4.1. |
|   R1 processa LSP de R3     |  147  |   33,2970 s    | R1 recebe, recalcula e reenvia o LSP de R3 (+6,88 ms). (Neste instante R1 ainda tem o LSP antigo de R2→R4, usando temporariamente custo 7.)|
|   t1' — Detecção em R2      |  151  |   33,3483 s    | R2 dá timeout em R4 e gera LSP:10.5.2.1:1795451165 sem 10.5.4.1.|
|   t2 — Convergência em R1   |  155  |   33,3536 s    | R1 recebe, recalcula e reenvia o LSP de R2 (+5,27 ms). R1 converge para a rota final (10.5.5.1, custo 9).|
|   t1'' — Detecção em R5     |  158  |   33,4078 s    | R5 dá timeout em R4 e gera LSP:10.5.5.1:1795451989 sem 10.5.4.1.|
|   t2' — Convergência global |  162  |   33,4253 s    | R1 recebe (via R3) e processa o LSP de R5 (+17,52 ms). Toda a rede converge na ida e na volta.|

 ### 3. Separação dos tempos: Detecção vs. Inundação e Recálculo                                                                             
                                                                                                                                              
  Medindo a partir do último HELLO recebido de R4 (t0 = 12,7656 s):                                                                           
                                                                                                                                              
  • Tempo de detecção da falha (t1 - t0):                                                                                                     
      • Em R3: 33,2901 - 12,7656 = 20,52 s                                                                                                    
      • Em R2: 33,3483 - 12,7656 = 20,58 s                                                                                                    
      • Em R5: 33,4078 - 12,7656 = 20,64 s                                                                                                    
      • (Em relação à queda efetiva observada em 13,16 s, a detecção levou ~20,13 s a 20,25 s.)                                               
  • Tempo de inundação + recálculo de Dijkstra (t2 - t1):                                                                                     
      • Onda de R3 até R1: 6,88 ms (33,2901 s → 33,2970 s)                                                                                    
      • Onda de R2 até R1 (rota final em R1): 5,27 ms (33,3483 s → 33,3536 s)                                                                 
      • Onda de R5 até R1 (convergência global): 17,52 ms (33,4078 s → 33,4253 s)                                                             
  • Tempo total até a convergência completa: 20,59 s para a tabela de R1 convergir (t2 - t0) e 20,66 s para toda a rede convergir (t2' - t0). 
                                                                                                                                              
  Proporção: ~99,9% do tempo de convergência corresponde à detecção da falha, enquanto a inundação dos LSPs e o recálculo de Dijkstra juntos  
  representam menos de 0,1% (poucos milissegundos).  
  
                                                                                           
  ### 4. Relação com os temporizadores do HELLO
  
  • O protocolo envia HELLO a cada 5 s (INTERVALO_HELLO = 5) e declara um vizinho inativo após 20 s sem receber HELLO (TIMEOUT_VIZINHO = 20,  
  equivalente a 4 períodos perdidos).
  • Além disso, o loop loop_monitorar_vizinhos() verifica timeouts a cada 1 s.
  • Por isso, o tempo observado em todos os vizinhos de R4 (20,52 s, 20,58 s e 20,64 s desde o último HELLO) bate exatamente com 20 s + até 1 
  s da granularidade do loop de monitoramento (e explica a pequena diferença de ~60 ms entre R3, R2 e R5 detectarem a queda).
  • Trade-off dos temporizadores: reduzir o intervalo de HELLO e o timeout aceleraria drasticamente a convergência (já que a detecção domina  
  99,9% do tempo), mas aumentaria o tráfego de controle periódico e o risco de falsos positivos em redes com perda ocasional de pacotes UDP.  
