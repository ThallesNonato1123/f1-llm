# f1-llm

Chatbot que responde perguntas em linguagem natural sobre Fórmula 1 e plota gráficos, usando dados da biblioteca FastF1.

## Language

**Sessão**:
Um segmento distinto de um final de semana de corrida (Corrida, Classificação ou Sprint), com seus próprios dados de tempo independentes.
_Avoid_: Prova, etapa.

**Grande Prêmio**:
O evento completo de um final de semana em um circuito específico, composto por uma ou mais Sessões.
_Avoid_: GP (como termo de glossário), evento, corrida (quando usado para o fim de semana inteiro).

**Volta**:
Um circuito completo da pista por um carro; a unidade básica de cronometragem dentro de uma Sessão.
_Avoid_: Giro.

**Telemetria**:
Dados contínuos do carro capturados ao longo de uma Volta (velocidade, marcha, acelerador, freio).
_Avoid_: Dados do carro.

**Velocidade máxima**:
A maior velocidade instantânea de Telemetria registrada por um Piloto durante uma Volta.
_Avoid_: Top speed.

**Velocidade média**:
A distância total de uma Volta dividida pelo seu tempo total — a velocidade real da volta inteira, não um valor instantâneo. Diferente da Velocidade máxima, que é o pico de um único instante.
_Avoid_: Mean speed, velocidade média das amostras.

**Aceleração lateral**:
A aceleração do carro perpendicular à direção do movimento, gerada ao fazer uma curva. Medida em g (1g = 9,81 m/s²); maior magnitude indica uma curva feita com mais força, exigindo mais aderência do pneu.
_Avoid_: Lateral acceleration, força g lateral.

**Aceleração longitudinal**:
A aceleração do carro na direção do movimento. Positiva sob tração (acelerando), negativa sob frenagem. Medida em g.
_Avoid_: Longitudinal acceleration.

**Aceleração combinada**:
A magnitude do vetor que soma a Aceleração lateral e a Aceleração longitudinal num mesmo instante — quantifica o quanto o carro está sendo exigido (por exemplo, freando e curvando ao mesmo tempo), independente da direção.
_Avoid_: Combined acceleration, aceleração total.

**Envelope de aceleração**:
O contorno mais externo dos pontos de Aceleração lateral × Aceleração longitudinal de um Piloto ao longo de uma Volta — representa o limite de desempenho que o carro atingiu naquela volta. Pontos mais distantes do centro indicam mais aderência.
_Avoid_: Envelope (sozinho), performance envelope.

**Parada nos boxes**:
O Piloto entra no pit lane e, geralmente, troca o Composto de pneu antes de voltar à pista; encerra um Stint e inicia o próximo. Nos gráficos, é marcada pela primeira Volta do novo Stint — a volta em que o Piloto volta à pista.
_Avoid_: Pit stop, pitstop, box (como termo de glossário).

**Stint**:
Uma sequência contínua de Voltas de um Piloto com um único Composto de pneu, sem **Parada nos boxes**.
_Avoid_: Etapa de pneu, período.

**Composto de pneu**:
A categoria de pneu usada durante um Stint (ex: macio, médio, duro), que determina seu desempenho e degradação. Cada Composto é identificado pela cor oficial da Pirelli na lateral do pneu: macio vermelho, médio amarelo, duro branco, intermediário verde e chuva azul.
_Avoid_: Tipo de pneu.

**Ritmo de corrida**:
A diferença acumulada, Volta a Volta, entre um Piloto e um piloto de referência fictício que em cada Volta faz o tempo médio dos Pilotos que ainda estão na mesma volta do líder (retardatários ficam de fora), incluindo voltas de box e sob Safety car ou Virtual safety car. Estar à frente da referência indica ritmo melhor; estar atrás, ritmo pior.
_Avoid_: Pace, race trace, gap, desempenho de corrida.

**Gap para o vencedor**:
A diferença acumulada, Volta a Volta, entre um Piloto e o vencedor real da sessão (o Piloto classificado em 1º), incluindo voltas de box e sob Safety car ou Virtual safety car. É sempre zero ou negativo, exceto para o próprio vencedor, que fica em zero a corrida inteira. Diferente de **Ritmo de corrida**, que usa um piloto de referência fictício em vez do vencedor real.
_Avoid_: Pace, race trace, ritmo de corrida.

**Pneu novo**:
Um jogo de pneus que não foi usado em nenhuma Volta antes do início do Stint. O oposto é **Pneu usado**.
_Avoid_: Pneu fresco, pneu zero.

**Idade do pneu**:
O número de Voltas que um jogo de pneus específico já rodou, incluindo Voltas em outras Sessões se o jogo tiver sido reaproveitado (ex: um jogo usado na Classificação e levado para a Corrida não começa a Corrida com Idade do pneu zero). Dentro de um Stint, a Idade do pneu aumenta uma Volta por Volta. Um **Pneu novo** tem Idade do pneu zero no início do Stint.
_Avoid_: Idade do pneu desde o início do Stint.

**Safety car**:
Período em que o carro de segurança entra na pista e os Pilotos seguem atrás dele em fila, sem ultrapassar, neutralizando a Sessão.
_Avoid_: SC (como termo de glossário), carro de segurança.

**Virtual safety car**:
Período de neutralização sem carro físico na pista, em que cada Piloto precisa respeitar um tempo mínimo por trecho. É distinto do Safety car.
_Avoid_: VSC (como termo de glossário), safety car virtual.

**Volta limpa**:
Uma Volta que representa o ritmo real do carro, sem efeitos atípicos: exclui a Volta de entrada e a de saída de box, Voltas sob Safety car ou Virtual safety car, e Voltas significativamente mais lentas que o ritmo do Piloto no Stint.
_Avoid_: Volta válida, volta de referência.

**Tempo de volta corrigido por combustível**:
Uma estimativa do Tempo de volta que o carro faria sem o peso do combustível, descontando o efeito de o carro ficar mais leve — e mais rápido — ao longo da Sessão. Permite comparar Voltas do início e do fim de um Stint longo sem o viés do combustível.
_Avoid_: Tempo de volta ajustado, lap time normalizado.

**Degradação de pneu**:
O quanto o Tempo de volta corrigido por combustível piora a cada Volta de Idade do pneu dentro de um mesmo Composto, para um Piloto ou Equipe, calculada só sobre Voltas limpas. Maior degradação indica queda de desempenho mais rápida ao longo do Stint.
_Avoid_: Desgaste de pneu, wear.

**Piloto**:
Pessoa que compete em uma Sessão, identificada por nome, número ou código de três letras (ex: VER, HAM).
_Avoid_: Corredor.

**Equipe**:
O construtor que inscreve dois Pilotos numa temporada; acumula pontos próprios, distintos dos pontos de cada Piloto.
_Avoid_: Construtor (como termo preferido — usar Equipe), time.

**Classificação do campeonato**:
O ranking acumulado de pontos de Pilotos ou Equipes ao longo de uma temporada.
_Avoid_: Standings, tabela.
