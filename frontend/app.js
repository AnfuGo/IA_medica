//const API_URL = "https://SEU-TUNNEL.trycloudflare.com";
const API_URL = "https://127.0.0.1:5000";

async function enviarPergunta() {
    const pergunta = document.getElementById("inputPergunta").value;

    document.getElementById("pergunta").innerText = pergunta;

    try {
        const response = await fetch(`${API_URL}/api/pergunta/audio`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                pergunta: pergunta,
                tts_engine: "auto"
            })
        });

        if (!response.ok) {
            throw new Error("Erro na API");
        }

        // pegar headers 
        const tts = response.headers.get("X-TTS-Engine");

        console.log("TTS usado:", tts);

        //converter stream em blob
        const audioBlob = await response.blob();

        const audioURL = URL.createObjectURL(audioBlob);

        const player = document.getElementById("audioPlayer");
        player.src = audioURL;

        document.getElementById("resposta").innerText =
            "(Resposta exibida apenas em áudio)";

        salvarConsulta(pergunta, audioURL);

    } catch (err) {
        console.error(err);
        alert("Erro ao enviar pergunta");
    }
}
function salvarConsulta(pergunta, audioURL) {
    const lista = document.getElementById("listaConsultas");

    const item = document.createElement("li");

    item.innerHTML = `
        ${pergunta}
        <button onclick="reproduzir('${audioURL}')">Ouvir</button>
    `;

    lista.appendChild(item);
}

function reproduzir(url) {
    const player = document.getElementById("audioPlayer");
    player.src = url;
}
function carregarPDF(url) {
    document.getElementById("pdfViewer").src = url;
}