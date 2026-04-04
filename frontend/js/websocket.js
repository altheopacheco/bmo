// websocket.js
class AgentWebSocket {
    constructor(url) {
        this.ws = new WebSocket(url);
        this.ws.binaryType = "arraybuffer";
        this.onJsonMessage = null;   // callback for JSON messages
        this.onBinaryMessage = null; // callback for audio chunks
        this.setupHandlers();
    }

    setupHandlers() {
        this.ws.onmessage = (event) => {
            if (typeof event.data === "string") {
                try {
                    const msg = JSON.parse(event.data);
                    if (this.onJsonMessage) this.onJsonMessage(msg);
                } catch (e) {
                    console.error("Failed to parse JSON message:", e, event.data);
                }
            } else {
                // binary audio chunk
                if (this.onBinaryMessage) this.onBinaryMessage(event.data);
            }
        };
    }

    sendAudioChunk(chunk) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(chunk);
        }
    }

    sendControl(type, payload = {}) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, ...payload }));
        }
    }

    close() {
        this.ws.close();
    }
}

export { AgentWebSocket };