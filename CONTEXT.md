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

**Stint**:
Uma sequência contínua de Voltas de um Piloto com um único Composto de pneu, sem parada nos boxes.
_Avoid_: Etapa de pneu, período.

**Composto de pneu**:
A categoria de pneu usada durante um Stint (ex: macio, médio, duro), que determina seu desempenho e degradação. Cada Composto é identificado pela cor oficial da Pirelli na lateral do pneu: macio vermelho, médio amarelo, duro branco, intermediário verde e chuva azul.
_Avoid_: Tipo de pneu.

**Ritmo de corrida**:
A consistência dos tempos de Volta de um Piloto durante a Corrida, desconsiderando voltas de entrada/saída de boxes e voltas sob safety car.
_Avoid_: Pace, desempenho de corrida.

**Pneu novo**:
Um jogo de pneus que não foi usado em nenhuma Volta antes do início do Stint. O oposto é **Pneu usado**.
_Avoid_: Pneu fresco, pneu zero.

**Safety car**:
Período em que o carro de segurança entra na pista e os Pilotos seguem atrás dele em fila, sem ultrapassar, neutralizando a Sessão.
_Avoid_: SC (como termo de glossário), carro de segurança.

**Virtual safety car**:
Período de neutralização sem carro físico na pista, em que cada Piloto precisa respeitar um tempo mínimo por trecho. É distinto do Safety car.
_Avoid_: VSC (como termo de glossário), safety car virtual.

**Piloto**:
Pessoa que compete em uma Sessão, identificada por nome, número ou código de três letras (ex: VER, HAM).
_Avoid_: Corredor.

**Equipe**:
O construtor que inscreve dois Pilotos numa temporada; acumula pontos próprios, distintos dos pontos de cada Piloto.
_Avoid_: Construtor (como termo preferido — usar Equipe), time.

**Classificação do campeonato**:
O ranking acumulado de pontos de Pilotos ou Equipes ao longo de uma temporada.
_Avoid_: Standings, tabela.
