# Project Process Flow

This flowchart illustrates the lifecycle of a single user interaction with the assistant.

```mermaid
flowchart TD
    Start([Start]) --> Idle{State: IDLE}
    
    Idle -->|GPIO 24 Pressed| Debounce[Debounce Signal\n(50ms wait)]
    Debounce -->|Confirmed| LED_On[Turn LED ON]
    LED_On --> Record[Start Recording Audio]
    
    Record --> Monitor{Monitor Loop}
    Monitor -->|Time < 0.5s| Ignore[Ignore Release]
    Monitor -->|GPIO 24 Low| Continue_Rec[Continue Recording]
    Monitor -->|GPIO 24 High\n(Released)| Stop_Rec[Stop Recording]
    
    Ignore --> Monitor
    Continue_Rec --> Monitor
    
    Stop_Rec --> LED_Off[Turn LED OFF]
    LED_Off --> Transcribe[ASR Transcription\n(Vosk)]
    
    Transcribe -->|Text| Norm[Normalize Numbers\n'sixty'->'60']
    Norm --> Intent[Analyze Intent\n(Keyword/Regex)]
    
    Intent -->|Check Stock| DB_Query[Query Database]
    Intent -->|Unknown| Error_Resp[Generate Error Response]
    
    DB_Query -->|Results Found| Format[Format Natural Response]
    DB_Query -->|No Results| NotFound[Format 'Not Found' Response]
    
    Format --> TTS[Generate Speech]
    Error_Resp --> TTS
    NotFound --> TTS
    
    TTS --> Play[Play Audio]
    Play --> Idle
```
