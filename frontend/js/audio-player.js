import { startVisemeAnimation, stopVisemeAnimation } from "./viseme.js";

const audioElement = document.getElementById("player");

class AudioPlayer {
    constructor() {
        this.queue = [];
        this.isPlaying = false;
    }

    async init() {
        console.log("Audio player initialized.")
        return Promise.resolve();
    }

    async playChunk(arrayBuffer, timeline = null) {
        const blob = new Blob([arrayBuffer], { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        const playItem = { url, timeline };

        this.queue.push(playItem);
        if (!this.isPlaying) {
            this.isPlaying = true;
            this.playNext();
        }
    }

    playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            return;
        }
        const { url, timeline } = this.queue.shift();
        audioElement.src = url;

        audioElement.onplay = () => {
            if (timeline) startVisemeAnimation(audioElement, timeline);
        };

        audioElement.onended = () => {
            stopVisemeAnimation();
            URL.revokeObjectURL(url);
            this.playNext();
        };

        audioElement.onerror = (e) => {
            console.error("Audio playback error:", e);
            URL.revokeObjectURL(url);
            this.playNext();
        };

        audioElement.play().catch(err => console.error("play() failed:", err));
    }
}

export const player = new AudioPlayer();