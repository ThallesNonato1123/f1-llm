> **Status: parcialmente superseded pela [ADR 0006](0006-react-vite-frontend.md)** — o frontend deixou de ser HTML/CSS/JS puro sem build step. A separação backend (FastAPI) / frontend, e o Plotly gerado no backend, continuam valendo.

# Backend em FastAPI, frontend em HTML/CSS/JS puro, gráficos via Plotly

Consideramos um app single-process em Streamlit, mais rápido de entregar mas com controle visual limitado e acoplamento forte entre lógica e apresentação. Optamos por separar em backend (FastAPI) e frontend estático (HTML/CSS/JS puro, sem build step), com o Plotly gerado no backend e renderizado interativamente no navegador via `plotly.js`. Isso custa mais código de integração no início, mas mantém o backend reutilizável (ex: por outro frontend ou CLI no futuro) e evita prender a UI às limitações de um framework de dashboards.
