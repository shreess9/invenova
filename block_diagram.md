# System Block Diagram

```mermaid
graph TD
    subgraph "Hardware Interface"
        Mic[Microphone] -->|Audio Data| ALSA[ALSA Audio Driver]
        Btn_Pwr[Power Switch\nGPIO 23] -->|Signal| Launcher
        Btn_Rec[Record Button\nGPIO 24] -->|Signal| App
        LED[Status LED\nGPIO 27] <---|State| App
        Speaker <---|Audio| ALSA
    end

    subgraph "Software Control Plane"
        Launcher[Launcher Service\n(pi_launcher.py)] -- Spawns/Kills --> App[Main Application\n(mini_assistant.py)]
    end

    subgraph "Core Engines"
        App -->|Raw Audio| ASR[ASR Engine\n(Vosk API)]
        ASR -->|Text Transcript| Norm[Normalizer\n(num2words)]
        Norm -->|Clean Text| NLP[NLP Intent Engine]
        NLP -->|SQL Query| DB[(SQLite Database)]
        DB -->|Results| NLP
        NLP -->|Response Text| TTS[TTS Engine\n(Piper/eSpeak)]
        TTS -->|PCM Audio| ALSA
    end

    classDef hardware fill:#f9f,stroke:#333,stroke-width:2px;
    classDef software fill:#bbf,stroke:#333,stroke-width:2px;
    classDef data fill:#dfd,stroke:#333,stroke-width:2px;

    class Mic,Btn_Pwr,Btn_Rec,LED,Speaker hardware;
    class Launcher,App,ASR,NLP,TTS,Norm software;
    class DB,ALSA data;
```
