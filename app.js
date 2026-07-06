const API_URL = "https://findarticles-numerous-observation-palm.trycloudflare.com"; 
let relatorioFinal = "";
let processandoTranscricao = false;

// Inicializa o verificador cíclico de áudio vindo do ESP32 (a cada 2 segundos)
let intervaloTranscricao = setInterval(verificarTranscricao, 2000); 

async function verificarTranscricao() {
    if (processandoTranscricao) return;
    processandoTranscricao = true;

    let precisaReiniciarInterval = true; 

    try {
        // 1. Apenas lê se há algum texto acumulado vindo do Whisper no backend
        const response = await fetch(`${API_URL}/api/transcricao`);
        if (!response.ok) {
            console.warn(`Backend indisponível ou retornou erro HTTP: ${response.status}`);
            return; 
        }

        const data = await response.json();
        
        // Se o Whisper transcreveu algo válido:
        if (data.texto && data.texto.trim() !== "") {
            console.log("Texto detectado! Iniciando processamento do Pipeline...", data.texto);
            
            // Pausa o intervalo principal temporariamente para evitar concorrência
            clearInterval(intervaloTranscricao); 
            precisaReiniciarInterval = false; 

            document.getElementById("backendStatus").innerText = "Processando IA...";
            
            let processado = false;
            let dadosFinais = null;
            let tentativas = 0;

            // 2. Loop de Polling Interno Protegido (Aguarda o status 200 do backend)
            while (!processado && tentativas < 40) {
                tentativas++;
                try {
                    const respostaIA = await fetch(`${API_URL}/api/transcricao/processar`);
                    
                    if (respostaIA.status === 202) {
                        console.log(`[Tentativa ${tentativas}] Servidor backend gerando resposta e áudio...`);
                        await new Promise(resolve => setTimeout(resolve, 1500)); 
                    } else if (respostaIA.status === 200) {
                        dadosFinais = await respostaIA.json();
                        
                        // SE for o fim da consulta, só consideramos "Totalmente Processado" 
                        // quando a thread de background terminar e entregar o relatório de texto!
                        if (dadosFinais.fim && !dadosFinais.relatorio) {
                            console.log("Áudio pronto, mas a thread ainda está processando o relatório...");
                            
                            // Atualiza o áudio logo na tela caso queira que o navegador já toque antes de exibir o relatório
                            if (dadosFinais.audio_url && !document.getElementById("audioPlayer").src.includes(dadosFinais.audio_url)) {
                                executarAudioResposta(dadosFinais);
                            }
                            await new Promise(resolve => setTimeout(resolve, 1500));
                        } else {
                            processado = true; // Tudo pronto! (Ou consulta comum, ou consulta com relatório pronto)
                        }
                    } else {
                        console.error(`O servidor retornou um status inesperado: HTTP ${respostaIA.status}`);
                        break; 
                    }
                } catch (errInner) {
                    console.error("Falha de rede momentânea no loop interno:", errInner);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                }
            }

            // 3. Renderiza os dados finais recebidos da IA
            if (processado && dadosFinais) {
                document.getElementById("backendStatus").innerText = "Online";
                document.getElementById("pergunta").innerText = dadosFinais.pergunta || "";
                document.getElementById("resposta").innerText = dadosFinais.resposta || "";

                if (dadosFinais.tts_engine) {
                    document.getElementById("ttsEngine").innerText = dadosFinais.tts_engine.toUpperCase();
                }

                executarAudioResposta(dadosFinais);

                if (dadosFinais.relatorio) {
                    console.log("CONSURTA CONCLUÍDA! Relatório Recebido da Thread.");
                    relatorioFinal = dadosFinais.relatorio;
                    
                    const btnPDF = document.getElementById("btnBaixarPDF");
                    if (btnPDF) btnPDF.disabled = false;
                    
                    const relatorioDiv = document.getElementById("relatorio");
                    if (relatorioDiv) relatorioDiv.innerText = dadosFinais.relatorio;
                }

                // 4. Decisão de reativar o monitoramento baseada na chave "fim"
                if (!dadosFinais.fim) {
                    intervaloTranscricao = setInterval(verificarTranscricao, 2000);
                } else {
                    document.getElementById("backendStatus").innerText = "Consulta Concluída";
                }
            } else {
                console.warn("Falha ao processar pipeline por estouro de tentativas. Retomando checagem...");
                intervaloTranscricao = setInterval(verificarTranscricao, 2000);
            }
        }
    } catch (err) {
        console.error("Erro grave ao verificar transcrição:", err);
        document.getElementById("backendStatus").innerText = "Erro na conexão";
    } finally {
        processandoTranscricao = false;
        if (precisaReiniciarInterval) {
            clearInterval(intervaloTranscricao);
            intervaloTranscricao = setInterval(verificarTranscricao, 2000);
        }
    }
}

function executarAudioResposta(dados) {
    if (!dados.audio_url) return;
    const player = document.getElementById("audioPlayer");
    
    // Evita recarregar o mesmo áudio se ele já estiver tocando
    if (player.src.includes(dados.audio_url)) return; 

    player.src = `${API_URL}${dados.audio_url}`;
    try {
        player.play();
    } catch (e) {
        console.log("Autoplay impedido pelo navegador.");
    }
    salvarConsulta(dados.pergunta || "Consulta de Áudio", `${API_URL}${dados.audio_url}`);
}

function salvarConsulta(pergunta, audioURL) {
    const lista = document.getElementById("listaConsultas");
    if (!lista) return;
    const item = document.createElement("li");
    item.innerHTML = `
        <strong>Pergunta:</strong> ${pergunta} <br>
        <button onclick="reproduzir('${audioURL}')" style="margin-top: 5px; padding: 2px 8px;">🔊 Ouvir</button>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">
    `;
    lista.appendChild(item);
}

function reproduzir(url) {
    const player = document.getElementById("audioPlayer");
    player.src = url;
    player.play().catch(err => console.log("Erro ao reproduzir histórico:", err));
}