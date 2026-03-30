const eventSource = new EventSource("/llm-ready")

eventSource.onmessage = e => {
    const data = JSON.parse(e.data);
    const status = document.getElementById("status");

    if (data.system_init_message == "Initialized") {
        status.textContent = "BMO is Ready!"
        eventSource.close()
    } else {
        status.textContent = data.system_init_message
    }
}