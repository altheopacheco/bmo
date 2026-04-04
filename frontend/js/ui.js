// ui.js
const chatHistory = document.getElementById("chat-history");
const traceList = document.getElementById("trace-list");
const stateText = document.getElementById("state-text");
const transcriptionMetric = document.getElementById("transcription-metric");
const llmMetric = document.getElementById("llm-metric");
const audioMetric = document.getElementById("audio-metric");
const statusMessage = document.getElementById("status-message");

export let currentChatBubble = null;   // the <li> for the current BMO message

export function addUserMessage(text) {
    const li = document.createElement("li");
    li.textContent = `User: ${text}`;
    chatHistory.prepend(li);
}

export function startAssistantMessage() {
    currentChatBubble = document.createElement("li");
    currentChatBubble.textContent = "BMO: ";
    chatHistory.prepend(currentChatBubble);
}

export function appendAssistantToken(token) {
    if (currentChatBubble) {
        currentChatBubble.textContent += token;
    }
}

export function finishAssistantMessage() {
    currentChatBubble = null;
}

export function addReasoning(text) {
    const li = document.createElement("li");
    li.style.color = "#666";
    li.style.fontStyle = "italic";
    li.textContent = `[Reasoning] ${text}`;
    chatHistory.prepend(li);
}

export function addToolCall(name, args) {
    const li = document.createElement("li");
    li.textContent = `🔧 Tool call: ${name}(${JSON.stringify(args)})`;
    traceList.prepend(li);
}

export function addToolResult(result) {
    const li = document.createElement("li");
    li.textContent = `📥 Tool result: ${result.substring(0, 100)}${result.length > 100 ? "…" : ""}`;
    traceList.prepend(li);
}

export function updateState(stateMsg) {
    stateText.textContent = `BMO state: ${stateMsg}`;
    statusMessage.textContent = stateMsg;
}

export function updateMetric(type, value) {
    const formatted = typeof value === "number" ? value.toFixed(3) : value;
    if (type === "transcription") transcriptionMetric.textContent = `Transcription: ${formatted}s`;
    else if (type === "llm") llmMetric.textContent = `LLM TTFT: ${formatted}s`;
    else if (type === "audio") audioMetric.textContent = `TTS: ${formatted}s`;
}

export function clearTrace() {
    traceList.innerHTML = "";
}

export function showError(message) {
    const li = document.createElement("li");
    li.style.color = "red";
    li.textContent = `Error: ${message}`;
    chatHistory.prepend(li);
}