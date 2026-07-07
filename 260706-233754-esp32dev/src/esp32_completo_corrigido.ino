#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>

// ==================================================================================
// CONFIGURAÇÕES DE REDE E SERVIDOR
// ==================================================================================
const char* ssid = "Borchardt";
const char* password = "Agb230504";
const char* serverHost = "https://approximate-stocks-pay-efficiency.trycloudflare.com";

#define BUTTON_PIN 4
#define MIC_SCK 26  
#define MIC_WS  25  
#define MIC_SD  22  
#define SPK_SD  27

// Pinos do módulo Cartão SD (VSPI)
#define SD_MISO 19
#define SD_MOSI 23
#define SD_SCK  18
#define SD_CS   5

#define SAMPLE_RATE 16000
#define BLOCK_SIZE 512 

int32_t micBuffer32[BLOCK_SIZE];
int16_t micBuffer16[BLOCK_SIZE];

const char* FILE_PATH = "/gravacao.wav";
File audioFile;
bool isRecording = false;

WiFiClientSecure client;

void connectWiFi();
void initI2SSystem();
void initSDCard();
void enviarAudioCompleto();
void processPipeline();
void writeWavHeader(File file, uint32_t totalAudioLen);
bool baixarEReproduzirAudio(String wavUrl);

void setup() {
    Serial.begin(115200);
    client.setInsecure();
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    
    connectWiFi();
    initSDCard();
    initI2SSystem();
    
    Serial.println("\n>>> Sistema pronto! Pressione e segure para falar. <<<");
}

void loop() {
    // Botão Pressionado (Segurando)
    if (digitalRead(BUTTON_PIN) == LOW) {
        
        // Dispara APENAS no primeiro instante do clique
        if (!isRecording) {
            isRecording = true;
            
            i2s_set_clk(I2S_NUM_0, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_32BIT, I2S_CHANNEL_MONO);
            Serial.println("\n[I2S] Gravando no SD em formato .WAV...");
            
            // Remove o arquivo anterior antes de criar um novo, garantindo início limpo
            // (evita acúmulo/corrupção entre perguntas de uma mesma conversa)
            if (SD.exists(FILE_PATH)) {
                SD.remove(FILE_PATH);
            }

            audioFile = SD.open(FILE_PATH, FILE_WRITE);
            if (audioFile) {
                uint8_t blankHeader[44] = {0};
                audioFile.write(blankHeader, 44);
                audioFile.flush();
                Serial.println("[SD] Arquivo criado. Capturando áudio...");
            } else {
                Serial.println("[ERRO SD] Falha crítica ao criar o arquivo .wav!");
            }
        }

        // Se estiver gravando e o arquivo estiver saudável, lê o microfone continuamente
        if (isRecording && audioFile) {
            size_t bytesRead = 0;
            
            esp_err_t res = i2s_read(I2S_NUM_0, micBuffer32, sizeof(micBuffer32), &bytesRead, 10 / portTICK_PERIOD_MS);

            if (res == ESP_OK && bytesRead > 0) {
                int samplesRead = bytesRead / sizeof(int32_t);

                for (int i = 0; i < samplesRead; i++) {
                    micBuffer16[i] = (int16_t)(micBuffer32[i] >> 11); 
                }

                size_t bytesConverted = samplesRead * sizeof(int16_t);
                size_t gravados = audioFile.write((uint8_t*)micBuffer16, bytesConverted);
                
                if (gravados == 0) {
                    Serial.print("!");
                }
            }
        }
    }
    // Botão Solto
    else {
        if (isRecording) {
            isRecording = false;
            Serial.println("\n[Botão Solto] Finalizando gravação...");
            
            if (audioFile) {
                // position() reflete o cursor de escrita atual (inclui dados
                // ainda não commitados fisicamente); size() ficaria "atrasado"
                size_t totalFileSize = audioFile.position();
                
                if (totalFileSize > 44) {
                    size_t audioDataLen = totalFileSize - 44;
                    
                    audioFile.flush();
                    audioFile.seek(0);
                    writeWavHeader(audioFile, audioDataLen);
                    audioFile.close();
                    
                    Serial.printf(">>> SUCESSO: .WAV gravado com %d bytes totais.\n", totalFileSize);
                    
                    enviarAudioCompleto();
                } else {
                    audioFile.close();
                    Serial.printf("[AVISO] Gravação vazia! Apenas %d bytes salvos.\n", totalFileSize);
                }
            }
            
            processPipeline();
        }
    }
}

// Função auxiliar para gerar e gravar o Cabeçalho estruturado do formato WAV (PCM 16-bit Mono)
void writeWavHeader(File file, uint32_t totalAudioLen) {
    uint32_t totalDataLen = totalAudioLen + 36;
    uint32_t longSampleRate = SAMPLE_RATE;
    uint32_t byteRate = SAMPLE_RATE * 1 * sizeof(int16_t);

    uint8_t header[44];
    header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
    header[4] = (totalDataLen & 0xff);
    header[5] = ((totalDataLen >> 8) & 0xff);
    header[6] = ((totalDataLen >> 16) & 0xff);
    header[7] = ((totalDataLen >> 24) & 0xff);
    header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';
    header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
    header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0;
    header[20] = 1; header[21] = 0;
    header[22] = 1; header[23] = 0;
    header[24] = (longSampleRate & 0xff);
    header[25] = ((longSampleRate >> 8) & 0xff);
    header[26] = ((longSampleRate >> 16) & 0xff);
    header[27] = ((longSampleRate >> 24) & 0xff);
    header[28] = (byteRate & 0xff);
    header[29] = ((byteRate >> 8) & 0xff);
    header[30] = ((byteRate >> 16) & 0xff);
    header[31] = ((byteRate >> 24) & 0xff);
    header[32] = 2; header[33] = 0;
    header[34] = 16; header[35] = 0;
    header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
    header[40] = (totalAudioLen & 0xff);
    header[41] = ((totalAudioLen >> 8) & 0xff);
    header[42] = ((totalAudioLen >> 16) & 0xff);
    header[43] = ((totalAudioLen >> 24) & 0xff);

    file.write(header, 44);
}

void connectWiFi() {
    Serial.print("Conectando Wi-Fi");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.println("\nWi-Fi Conectado!");
}

void initSDCard() {
    Serial.println("Inicializando pinos do SPI para o SD...");
    SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
    if (!SD.begin(SD_CS)) {
        Serial.println("[ERRO] Falha ao montar o Cartão SD!");
        while (true); 
    }
    Serial.println("Cartão SD pronto.");
}

void initI2SSystem() {
    i2s_config_t config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, 
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 64,
        .use_apll = false
    };

    i2s_pin_config_t pins = {
        .bck_io_num = MIC_SCK, .ws_io_num = MIC_WS, .data_out_num = SPK_SD, .data_in_num = MIC_SD
    };

    i2s_driver_install(I2S_NUM_0, &config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pins);
    Serial.println("I2S Inicializado.");
}


void enviarAudioCompleto() {
    audioFile = SD.open(FILE_PATH, FILE_READ);
    if (!audioFile) {
        Serial.println("[ERRO] Não foi possível ler o arquivo WAV.");
        return;
    }

    size_t totalAudioSize = audioFile.size();
    Serial.printf("\nEnviando arquivo completo (%d bytes) em uma unica requisicao...\n", totalAudioSize);

    HTTPClient http;
    String uploadUrl = String(serverHost) + "/api/audio/chunk";
    http.begin(client, uploadUrl);
    http.setTimeout(60000); // upload do arquivo inteiro pode levar mais tempo que um chunk pequeno

    http.addHeader("Content-Type", "audio/wav");
    http.addHeader("X-Chunk-Index", "0");
    http.addHeader("X-Chunk-Reset", "true");
    http.addHeader("X-Chunk-Final", "true");

    // Envia o arquivo inteiro como corpo da requisição, lendo direto do SD
    int code = http.sendRequest("POST", &audioFile, totalAudioSize);

    http.end();
    audioFile.close();

    if (code == 200) {
        Serial.println("Envio concluido com sucesso (requisicao unica).");
    } else {
        Serial.printf("[ERRO] Falha no envio (HTTP=%d).\n", code);
    }
}

void processPipeline() {

    HTTPClient http;
    String audioUrl = "";
    String respostaTexto = "";

    const unsigned long TIMEOUT_TOTAL_MS = 180000; // 3 minutos — ajuste como quiser
    const unsigned long INTERVALO_POLL_MS = 1500;   // intervalo entre tentativas

    Serial.println("Aguardando processamento do Whisper e Ollama no servidor...");

    unsigned long inicio = millis();

    while (millis() - inicio < TIMEOUT_TOTAL_MS) {

        delay(INTERVALO_POLL_MS);

        http.begin(client, String(serverHost) + "/api/transcricao/processar");
        http.setTimeout(45000);

        int r = http.GET();

        if (r == 202) {
            Serial.println("Servidor ainda processando...");
            http.end();
        }
        else if (r == 200) {
            String json = http.getString();
            DynamicJsonDocument doc(4096);

            if (deserializeJson(doc, json) == DeserializationError::Ok) {
                audioUrl = doc["audio_url"].as<String>();
                respostaTexto = doc["resposta"].as<String>();
            }

            http.end();
            break;
        }
        else {
            Serial.printf("HTTP inesperado: %d\n", r);
            http.end();
        }
    }

    if (audioUrl == "") {
        Serial.println("\n[Timeout/Erro] Não foi possível obter resposta da IA.");
        return;
    }

    Serial.println("\n========================================");
    Serial.print("IA Respondeu: ");
    Serial.println(respostaTexto);
    Serial.println("========================================\n");

    String wavUrl = String(serverHost) + audioUrl;

    Serial.printf("Baixando áudio de resposta de: %s\n", wavUrl.c_str());

    bool sucesso = baixarEReproduzirAudio(wavUrl);

    if (!sucesso) {
        Serial.println("\n[ERRO] Não foi possível reproduzir o áudio de resposta.");
        return;
    }

    Serial.println("\n>>> Áudio finalizado! Pronto para a próxima pergunta. <<<");
}

// ==================================================================================
// Baixa e reproduz o áudio de resposta, com leitura resiliente do cabeçalho WAV
// (tolerante à latência do túnel Cloudflare) e retry em caso de falha.
// ==================================================================================
bool baixarEReproduzirAudio(String wavUrl) {

    const int MAX_TENTATIVAS = 3;

    for (int tentativa = 1; tentativa <= MAX_TENTATIVAS; tentativa++) {

        HTTPClient http;
        http.begin(client, wavUrl);
        http.setTimeout(15000);

        int httpCode = http.GET();

        if (httpCode != 200) {
            Serial.printf("[Tentativa %d/%d] Erro ao obter WAV (HTTP=%d).\n", tentativa, MAX_TENTATIVAS, httpCode);
            http.end();
            delay(500);
            continue;
        }

        int totalBytesParaLer = http.getSize();
        if (totalBytesParaLer <= 0) {
            Serial.println("Aviso: Tamanho do arquivo desconhecido. Usando modo de segurança.");
        }

        WiFiClient* stream = http.getStreamPtr();
        stream->setTimeout(10000); // timeout de leitura maior, adequado à latência do túnel

        // Leitura resiliente do cabeçalho: acumula os 44 bytes mesmo se
        // chegarem em pedaços menores, por causa da latência do túnel.
        uint8_t wavHeader[44];
        size_t headerLido = 0;
        unsigned long inicioHeader = millis();

        while (headerLido < 44 && (millis() - inicioHeader) < 10000) {
            if (stream->available()) {
                int n = stream->readBytes(wavHeader + headerLido, 44 - headerLido);
                headerLido += n;
            } else {
                delay(5);
            }
        }

        if (headerLido != 44) {
            Serial.printf("[Tentativa %d/%d] Cabeçalho incompleto (%d/44 bytes).\n", tentativa, MAX_TENTATIVAS, headerLido);
            http.end();
            delay(500);
            continue; // tenta novamente
        }

        if (totalBytesParaLer > 0) totalBytesParaLer -= 44;

        uint32_t sampleRate =
            wavHeader[24]
            | (wavHeader[25] << 8)
            | (wavHeader[26] << 16)
            | (wavHeader[27] << 24);

        Serial.printf("WAV = %lu Hz\n", sampleRate);

        i2s_set_clk(I2S_NUM_0, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);

        uint8_t buffer[1024];
        Serial.println("Reproduzindo áudio no Alto-falante...");

        int bytesLidosTotal = 0;

        while (http.connected() && (totalBytesParaLer <= 0 || bytesLidosTotal < totalBytesParaLer)) {

            int avail = stream->available();

            if (!avail) {
                delay(1);
                continue;
            }

            int maxParaLer = sizeof(buffer);
            if (totalBytesParaLer > 0) {
                int restante = totalBytesParaLer - bytesLidosTotal;
                if (restante < maxParaLer) maxParaLer = restante;
            }

            int len = stream->readBytes(buffer, min(avail, maxParaLer));
            if (len <= 0) break;

            bytesLidosTotal += len;

            size_t written;
            i2s_write(I2S_NUM_0, buffer, len, &written, portMAX_DELAY);
        }

        http.end();
        return true; // sucesso, não precisa tentar de novo
    }

    return false; // esgotou as tentativas
}
