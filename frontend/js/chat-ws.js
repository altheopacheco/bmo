const ws = new WebSocket(`ws://${window.location.host}/ws`);

const audioQueue = [];
let isPlaying = false;

chatElement = document.getElementById("chat-history");
currentChat = null;
inProgress = false;
doneThinking = false;

ws.onmessage = async (event) => {
    const data = event.data;
    if (data instanceof Blob) { //Audio

        const timeline = getPendingTimeline();

        data.type = "audio/wav";
        const url = URL.createObjectURL(event.data);
        audioQueue.push({url, timeline});
        if (!isPlaying) playNext();
    } else { //JSON
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    }
};

function handleMessage(msg) {
    if (msg.type === "user") {
        if (!inProgress) {
            createChat("User", msg.text)
        } else {
            appendCurrentChat(msg.text)
        }
        doneThinking = false;
    } 
    
    else if (msg.type === "start") {
        endChat();
    } else if (msg.type === "chunk") {
        if (!doneThinking) {
            createChat("BMO", msg.text);
            doneThinking = true;
        } else {
            appendCurrentChat(msg.text)
        }
        // document.getElementById("status").textContent = "BMO is talking...";
    } else if (msg.type === "reasoning") {
        if (!inProgress) {
            createChat("Reasoning", msg.text)
        } else {
            appendCurrentChat(msg.text)
        }
    } 
    
    else if (msg.type === "end_reply") {
        // document.getElementById("status").textContent = "BMO is done talking";
        endChat()
    }

    else if (msg.type == "viseme_timeline") {
        setPendingTimeline(msg.timeline)
    }

    else if (msg.type == "audio_metric") {
        document.getElementById("audio-metric").textContent = `Audio Elapsed Time: ${msg.time_elapsed.toFixed(4)}s`
    } else if (msg.type == "llm_metric") {
        document.getElementById("llm-metric").textContent = `LLM Elapsed Time: ${msg.time_elapsed.toFixed(4)}s`
    } else if (msg.type == "transcription_metric") {
        document.getElementById("transcription-metric").textContent = `Transcription Elapsed Time: ${msg.time_elapsed.toFixed(4)}s`
    }
    
    else if (msg.type === "error") {
        console.error(msg.message);
    } else {
        console.log(`Unhandled Message: ${msg}`)
    }
}

function playNext() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }

    isPlaying = true;
    const {url, timeline} = audioQueue.shift();
    const audio = document.getElementById("player");

    audio.src = url;

    audio.onplay = () => {
        if (timeline) startVisemeAnimation(audio, timeline);
    }

    audio.onended = () => {
        stopVisemeAnimation()
        URL.revokeObjectURL(url); 
        playNext();
    };

    audio.onerror = (e) => {
        console.error("Audio playback error:", e);
        stopVisemeAnimation()
        URL.revokeObjectURL(url);
        playNext(); // don't stall the queue on a bad chunk
    };

    audio.play().catch(err => console.error("play() failed:", err));
}

function createChat(type, text) {
    currentChat = document.createElement("li");
    currentChat.textContent = type + ": " + text;
    chatElement.prepend(currentChat);
    inProgress = true
}

function appendCurrentChat(msg) {
    currentChat.textContent += msg
}

function endChat() {
    inProgress = false
}