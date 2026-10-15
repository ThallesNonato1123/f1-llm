const NETWORK_ERROR_TEXT = "Não foi possível conectar ao servidor. Verifique se ele ainda está rodando.";

const thread = document.getElementById("thread");
const composer = document.getElementById("composer");
const questionField = document.getElementById("question");
const sendButton = document.getElementById("send");
const status = document.getElementById("status");
const statusLabel = document.getElementById("status-label");

let history = [];

function addBubble(role, { text, pending = false, error = false } = {}) {
  const row = document.createElement("div");
  row.className = `row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (pending) bubble.classList.add("pending");
  if (error) bubble.classList.add("error");
  bubble.textContent = text;

  row.appendChild(bubble);
  thread.appendChild(row);
  thread.scrollTop = thread.scrollHeight;
  return bubble;
}

function renderAssistantReply(bubble, { text, charts }) {
  bubble.classList.remove("pending");
  bubble.textContent = "";
  bubble.classList.add("answer-block");

  const textNode = document.createElement("div");
  textNode.textContent = text;
  bubble.appendChild(textNode);

  charts.forEach((figure, index) => {
    const card = document.createElement("div");
    card.className = "chart-card";

    const plotDiv = document.createElement("div");
    plotDiv.className = "plot";
    plotDiv.id = `chart-${Date.now()}-${index}`;
    card.appendChild(plotDiv);

    bubble.appendChild(card);
    Plotly.newPlot(plotDiv, figure.data, figure.layout, { responsive: true });
  });

  thread.scrollTop = thread.scrollHeight;
}

function setComposerEnabled(enabled) {
  questionField.disabled = !enabled;
  sendButton.disabled = !enabled;
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("unhealthy");
    status.classList.add("connected");
    statusLabel.textContent = "conectado";
  } catch {
    status.classList.add("disconnected");
    statusLabel.textContent = "desconectado";
    setComposerEnabled(false);
  }
}

async function sendQuestion(question) {
  addBubble("user", { text: question });
  setComposerEnabled(false);
  const pendingBubble = addBubble("assistant", { text: "…", pending: true });

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });
    const body = await response.json();

    if (!response.ok) {
      pendingBubble.classList.remove("pending");
      pendingBubble.classList.add("error");
      pendingBubble.textContent = body.detail || NETWORK_ERROR_TEXT;
      return;
    }

    history = body.history;
    renderAssistantReply(pendingBubble, body);
  } catch {
    pendingBubble.classList.remove("pending");
    pendingBubble.classList.add("error");
    pendingBubble.textContent = NETWORK_ERROR_TEXT;
  } finally {
    setComposerEnabled(true);
    questionField.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionField.value.trim();
  if (!question) return;
  questionField.value = "";
  sendQuestion(question);
});

checkHealth();
