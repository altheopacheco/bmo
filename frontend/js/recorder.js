// recorder.js
let mediaRecorder = null;
let stream = null;
let ws = null;
let audioChunks = [];

export function initRecorder(webSocket) { ws = webSocket; }

export async function startRecording() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.start(100);
}

export async function stopRecordingAndSend() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
        return;
    }
    return new Promise((resolve) => {
        mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
            stream.getTracks().forEach(t => t.stop());
            const buffer = await blob.arrayBuffer();
            if (ws && ws.ws.readyState === WebSocket.OPEN) {
                ws.sendAudioChunk(buffer);  // send as a single binary message
            }
            resolve();
        };
        mediaRecorder.stop();
    });
}

export function sendStopSignal() {
    if (ws) ws.sendControl("stop");
}