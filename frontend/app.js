// Ajuste esta URL para o mesmo host usado no ESP32 (serverHost) durante os testes.
// Ex: se você usar um túnel Cloudflare, coloque a mesma URL aqui e no firmware.
// const API_URL = "https://SEU-TUNNEL.trycloudflare.com";
const API_URL = "https://approximate-stocks-pay-efficiency.trycloudflare.com";

console.log("VERSAO APP.JS: com dedupe de audio - v6");

let relatorioFinal = "";
let processandoTranscricao = false;

// Guarda a última URL de áudio já tocada/exibida.
// O backend mantém a mesma resposta disponível até a próxima pergunta ser
// processada, então usamos essa comparação para não tocar o mesmo áudio
// repetidamente a cada ciclo de polling (2s).
let lastAudioUrl = null;

// ==================================================================================
// Envio de pergunta via TEXTO (uso para testes sem o ESP32 físico)
// Requer a rota /api/pergunta/texto no backend (ver mensagem anterior).
// ==================================================================================
async function enviarPergunta() {
    const inputEl = document.getElementById("inputPergunta");
    const pergunta = inputEl.value.trim();

    if (!pergunta) {
        alert("Digite uma pergunta antes de enviar.");
        return;
    }

    document.getElementById("pergunta").innerText = pergunta;
    document.getElementById("resposta").innerText = "Aguardando resposta...";

    try {
        const response = await fetch(`${API_URL}/api/pergunta/texto`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ pergunta })
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP ${response.status}`);
        }

        // A pergunta foi apenas enfileirada aqui.
        // A resposta real (texto + áudio + eventual relatório) chega
        // pelo polling normal em verificarTranscricao().
        inputEl.value = "";

    } catch (err) {
        console.error(err);
        alert("Erro ao enviar pergunta");
        document.getElementById("resposta").innerText = "";
    }
}

// ==================================================================================
// Polling do backend — usado tanto para o fluxo de texto quanto para o áudio do ESP32
// ==================================================================================
async function verificarTranscricao() {
    if (processandoTranscricao) {
        return;
    }
    processandoTranscricao = true;

    try {
        const response = await fetch(`${API_URL}/api/transcricao/processar`);

        if (!response.ok) {
            throw new Error(`Erro HTTP ${response.status}`);
        }

        const data = await response.json();
        document.getElementById("backendStatus").innerText = "Online";

        // Enquanto não há pergunta nova ou o backend ainda está processando,
        // não há dados úteis para exibir — apenas ignora este ciclo.
        if (data.status === "aguardando" || data.status === "processando") {
            return;
        }

        // O backend agora mantém a mesma resposta disponível repetidamente
        // (não apaga mais após servir uma vez), para que ESP32 e frontend
        // possam consultar de forma independente. Por isso, sempre atualizamos
        // os textos na tela (não custa nada), mas SÓ tocamos o áudio e
        // registramos na lista se for realmente uma resposta nova.
        if (data.pergunta) {
            document.getElementById("pergunta").innerText = data.pergunta;
        }
        if (data.resposta) {
            document.getElementById("resposta").innerText = data.resposta;
        }

        if (data.tts_engine) {
            document.getElementById("ttsEngine").innerText = data.tts_engine.toUpperCase();
        }

        const audioUrlCompleta = data.audio_url ? `${API_URL}${data.audio_url}` : null;

        // Dedupe: só age se a URL do áudio for diferente da última já tratada.
        // Como cada resposta gera um arquivo com nome único (uuid), isso é
        // suficiente para detectar "resposta realmente nova".
        if (audioUrlCompleta && audioUrlCompleta !== lastAudioUrl) {
            lastAudioUrl = audioUrlCompleta;

            console.log("Pergunta:", data.pergunta);
            console.log("Resposta:", data.resposta);

            const player = document.getElementById("audioPlayer");
            player.src = audioUrlCompleta;

            try {
                await player.play();
            } catch {
                console.log("Autoplay bloqueado pelo navegador");
            }

            salvarConsulta(data.pergunta, audioUrlCompleta);

            if (data.relatorio) {
                console.log("RELATÓRIO FINAL:", data.relatorio);

                relatorioFinal = data.relatorio;

                const btnPDF = document.getElementById("btnBaixarPDF");
                if (btnPDF) btnPDF.disabled = false;

                const relatorioDiv = document.getElementById("relatorio");
                if (relatorioDiv) {
                    relatorioDiv.innerText = data.relatorio;
                }
            }
        }

    } catch (err) {
        console.error("Erro ao verificar transcrição:", err);
        document.getElementById("backendStatus").innerText = "Offline";
    } finally {
        processandoTranscricao = false;
    }
}

// Consulta o backend a cada 2 segundos
setInterval(verificarTranscricao, 2000);

// ==================================================================================
// Utilitários de UI
// ==================================================================================
function salvarConsulta(pergunta, audioURL) {
    const lista = document.getElementById("listaConsultas");
    if (!lista) return;

    const item = document.createElement("li");
    item.innerHTML = `
        ${pergunta}
        <button onclick="reproduzir('${audioURL}')">
            Ouvir
        </button>
    `;
    lista.appendChild(item);
}

function reproduzir(url) {
    const player = document.getElementById("audioPlayer");
    player.src = url;
    player.play().catch(() => {});
}

function carregarPDF(url) {
    document.getElementById("pdfViewer").src = url;
}

function baixarRelatorioPDF() {
    if (!relatorioFinal) {
        alert("Nenhum relatório disponível para baixar ainda.");
        return;
    }
 
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({
        unit: "mm",
        format: "a4"
    });
 
    const margemEsquerda = 15;
    const margemSuperior = 20;
    const larguraUtil = 180; // largura da página A4 (210mm) menos as margens
    const alturaLinha = 6;
    const alturaPagina = 297; // altura da página A4 em mm
 
    doc.setFontSize(14);
    doc.text("Relatório de Consulta - Assistente Médico IoT", margemEsquerda, margemSuperior);
 
    doc.setFontSize(10);
    const dataGeracao = new Date().toLocaleString("pt-BR");
    doc.text(`Gerado em: ${dataGeracao}`, margemEsquerda, margemSuperior + 8);
 
    doc.setFontSize(11);
 
    // Quebra o texto em linhas que cabem na largura útil da página
    const linhas = doc.splitTextToSize(relatorioFinal, larguraUtil);
 
    let y = margemSuperior + 18;
 
    linhas.forEach((linha) => {
        // Se a linha atual ultrapassar o fim da página, cria uma nova página
        if (y + alturaLinha > alturaPagina - margemSuperior) {
            doc.addPage();
            y = margemSuperior;
        }
        doc.text(linha, margemEsquerda, y);
        y += alturaLinha;
    });
 
    const nomeArquivo = `relatorio_consulta_${Date.now()}.pdf`;
    doc.save(nomeArquivo);
}