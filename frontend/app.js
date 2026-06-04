// const API_URL = "https://SEU-TUNNEL.trycloudflare.com";
const API_URL = "http://127.0.0.1:5000";

async function enviarPergunta() {

    const pergunta = document.getElementById("inputPergunta").value;

    document.getElementById("pergunta").innerText = pergunta;

    try {

        const response = await fetch(
            `${API_URL}/api/pergunta/audio`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    pergunta: pergunta,
                    tts_engine: "auto"
                })
            }
        );

        if (!response.ok) {
            throw new Error("Erro na API");
        }

        const tts = response.headers.get("X-TTS-Engine");

        console.log("TTS usado:", tts);

        const audioBlob = await response.blob();

        const audioURL = URL.createObjectURL(audioBlob);

        const player = document.getElementById("audioPlayer");

        player.src = audioURL;

        try {
            await player.play();
        } catch {
            console.log("Autoplay bloqueado pelo navegador");
        }

        document.getElementById("resposta").innerText =
            "(Resposta reproduzida em áudio)";

        salvarConsulta(pergunta, audioURL);

    } catch (err) {

        console.error(err);
        alert("Erro ao enviar pergunta");
    }
}

let processandoTranscricao = false;

async function verificarTranscricao() {

    if (processandoTranscricao) {
        return;
    }

    processandoTranscricao = true;

    try {

        const response = await fetch(
            `${API_URL}/api/transcricao/processar`
        );

        // backend retorna 400 quando não há transcrição
        if (response.status === 400) {
            return;
        }

        if (!response.ok) {
            throw new Error(
                `Erro HTTP ${response.status}`
            );
        }

        const data = await response.json();
        document.getElementById("backendStatus").innerText = "Online";

        console.log("Pergunta:", data.pergunta);
        console.log("Resposta:", data.resposta);

        document.getElementById("pergunta").innerText =
            data.pergunta;

        document.getElementById("resposta").innerText =
            data.resposta;
        
        if (data.tts_engine) {

        document.getElementById("ttsEngine").innerText = data.tts_engine.toUpperCase();
        }

        if (data.audio_url) {

            const player =
                document.getElementById("audioPlayer");

            player.src =
                `${API_URL}${data.audio_url}`;

            try {
                await player.play();
            } catch {
                console.log(
                    "Autoplay bloqueado pelo navegador"
                );
            }

            salvarConsulta(
                data.pergunta,
                `${API_URL}${data.audio_url}`
            );
        }

        if (data.relatorio) {

            console.log(
                "RELATÓRIO FINAL:",
                data.relatorio
            );

            const relatorioDiv =
                document.getElementById("relatorio");

            if (relatorioDiv) {
                relatorioDiv.innerText =
                    data.relatorio;
            }
        }

    } catch (err) {

        console.error(
            "Erro ao verificar transcrição:",
            err
        );

    } finally {

        processandoTranscricao = false;
    }
}

// consulta o backend a cada 2 segundos
setInterval(
    verificarTranscricao,
    2000
);

function salvarConsulta(pergunta, audioURL) {

    const lista =
        document.getElementById("listaConsultas");

    const item =
        document.createElement("li");

    item.innerHTML = `
        ${pergunta}
        <button onclick="reproduzir('${audioURL}')">
            Ouvir
        </button>
    `;

    lista.appendChild(item);
}

function reproduzir(url) {

    const player =
        document.getElementById("audioPlayer");

    player.src = url;

    player.play().catch(() => {});
}

function carregarPDF(url) {

    document.getElementById("pdfViewer").src =
        url;
}