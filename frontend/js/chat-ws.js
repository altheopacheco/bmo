const ws = new WebSocket(`ws://${window.location.host}/ws`);

const audioQueue = [];
let isPlaying = false;

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
        document.getElementById("user-text").textContent = `You: ${msg.text}`;
    } 
    
    else if (msg.type === "start") {
        document.getElementById("bmo-text").textContent = "BMO: ";
        document.getElementById("status").textContent = "BMO is thinking...";
    } else if (msg.type === "chunk") {
        document.getElementById("bmo-text").textContent += msg.text;
        document.getElementById("status").textContent = "BMO is talking...";
    } 
    
    else if (msg.type === "end_reply") {
        document.getElementById("status").textContent = "BMO is done talking";
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