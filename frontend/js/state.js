const eventSource = new EventSource("/state");
const stateElement = document.getElementById("state");

eventSource.onmessage = e => {
    const data = JSON.parse(e.data);

    let stateStr = data.state;
    if (data.message) {
        stateStr += " - " + data.message;
        createChat("State", stateStr)
        endChat()
    }
    stateElement.innerText = "Bmo is " + data.state
}