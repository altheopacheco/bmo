// recorder.js
let mediaRecorder = null;
let audioChunks = [];
let stream = null;

async function startRecording() {
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

  audioChunks = [];
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };

  mediaRecorder.start();
}

async function stopRecordingAndSend() {
    return new Promise((resolve) => {
        mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: "audio/webm" });
            stream.getTracks().forEach((t) => t.stop());

            const buffer = await blob.arrayBuffer();
            ws.send(buffer);  
            resolve();
        };
        mediaRecorder.stop();
    });
}

let isRecording = false;

document.addEventListener("keydown", async (e) => {
  if (e.code !== "Space" || e.repeat || isRecording) return;
  e.preventDefault();
  isRecording = true;
  await startRecording();
  setStatus("Recording...");
});

document.addEventListener("keyup", async (e) => {
  if (e.code !== "Space" || !isRecording) return;
  isRecording = false;
  setStatus("Transcribing...");
  await stopRecordingAndSend();
});

function setStatus(msg) {
  document.getElementById("status").textContent = msg;
}