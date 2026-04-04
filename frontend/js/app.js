import { AgentWebSocket } from "./websocket.js";
import { initRecorder, startRecording, stopRecordingAndSend, sendStopSignal } from "./recorder.js";
import { player } from "./audio-player.js";
import * as ui from "./ui.js";
import { setPendingTimeline, getPendingTimeline } from "./viseme.js";

let ws = null;
let isRecording = false;
let finalAnswerMode = false; // not strictly needed, but for UI

function connectWebSocket() {
    ws = new AgentWebSocket(`ws://${window.location.host}/ws`);
    ws.onJsonMessage = handleJsonMessage;
    ws.onBinaryMessage = handleBinaryAudio;
    ws.ws.addEventListener('open', () => {
        initRecorder(ws);
        player.init().then(() => console.log("Audio player ready")).catch(console.error);
        console.log("WebSocket ready, recorder initialised");
    });
}

function handleJsonMessage(msg) {
    console.log("Received:", msg.type, msg.payload);

    switch (msg.type) {
        case "status":
            ui.updateState(msg.payload);
            break;
        case "transcript":
            ui.addUserMessage(msg.payload);
            break;
        case "llm_token":
            if (!ui.currentChatBubble) ui.startAssistantMessage();
            ui.appendAssistantToken(msg.payload);
            break;
        case "reasoning":
            ui.addReasoning(msg.payload);
            break;
        case "tool_call":
            ui.addToolCall(msg.payload.name, msg.payload.args);
            break;
        case "tool_result":
            ui.addToolResult(msg.payload);
            break;
        case "final_answer_start":
            // optional: clear any partial chat bubble? we'll just continue appending
            finalAnswerMode = true;
            break;
        case "viseme_timeline":
            setPendingTimeline(msg.payload);
            break;
        case "metric":
            if (msg.payload.name === "transcription") ui.updateMetric("transcription", msg.payload.value);
            else if (msg.payload.name === "ttft") ui.updateMetric("llm", msg.payload.value);
            else if (msg.payload.name === "tts") ui.updateMetric("audio", msg.payload.value);
            break;
        case "done":
            ui.finishAssistantMessage();
            finalAnswerMode = false;
            break;
        case "error":
            ui.showError(msg.payload);
            break;
        default:
            console.warn("Unhandled message type:", msg.type);
    }
}

function handleBinaryAudio(audioBuffer) {
    // Audio chunk from TTS (final answer or intermediate)
    console.log("Binary audio received, size:", audioBuffer.byteLength);
    const timeline = getPendingTimeline();   // retrieve and clear pending timeline
    if (timeline) {
        // You need to associate timeline with the audio being played
        // The player needs to know which timeline corresponds to which audio chunk
        player.playChunk(audioBuffer, timeline);
    } else {
        player.playChunk(audioBuffer);
    }
}

// Recording: hold Space to record, release to send stop
document.addEventListener("keydown", async (e) => {
    if (e.code !== "Space" || e.repeat || isRecording) return;
    e.preventDefault();
    isRecording = true;
    await startRecording();
});

document.addEventListener("keyup", async (e) => {
    if (e.code !== "Space" || !isRecording) return;
    e.preventDefault();
    isRecording = false;
    await stopRecordingAndSend();  
    sendStopSignal();   
});

// Initialise connection and audio player
connectWebSocket();