# Plotly em vez do matplotlib nativo da FastF1

A FastF1 já oferece helpers de plotagem prontos em matplotlib para telemetria, ritmo de corrida e estratégia de pneus. Optamos por Plotly mesmo assim, gerando os gráficos manualmente a partir dos dados da FastF1 (sem usar os helpers), para termos gráficos interativos (zoom, hover com valores exatos) renderizados no navegador via `plotly.js`. O custo é reimplementar do zero os 7 tipos de gráfico em vez de aproveitar o que a biblioteca já entrega pronto — decisão deliberada em favor da experiência do usuário no frontend.
