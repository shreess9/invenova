# Components Used

## Hardware Components

| Component | Specification | Purpose |
| :--- | :--- | :--- |
| **Raspberry Pi 4 Model B** | 4GB RAM, Quad-core Cortex-A72 | Main processing unit for ASR, NLP, and Logic. |
| **Micro SD Card** | 32GB Class 10 (SanDisk Ultra) | OS and Storage. |
| **USB Microphone** | Generic USB Mini Mic | Audio input capture. |
| **Speaker** | 3.5mm Jack / USB Powered | Audio output (TTS response). |
| **Push Button (Red)** | Tactile Momentary Switch | **Interact Button** (GPIO 24). Press to Start/Stop Recording. |
| **Toggle Switch / Button (Green)** | Latching or Deadman Switch | **System Power** (GPIO 23). Activates the software service. |
| **LED (Yellow)** | 5mm LED + 330Ω Resistor | **Status Indicator** (GPIO 27). Lit when listening/ready. |
| **Breadboard & Jumpers** | Generic | Prototyping connections. |

## Software Stack

| Component | Technology | Version / Details |
| :--- | :--- | :--- |
| **Operating System** | Raspberry Pi OS (Legacy/Bullseye) | Optimized for GPIO and Audio stability. |
| **Language** | Python | v3.9+ |
| **Speech Recognition (ASR)** | **Vosk API** | `vosk-model-small-en-us-0.15` (Offline). |
| **Text-to-Speech (TTS)** | **Piper / eSpeak NG** | Low-latency local synthesis. |
| **Database** | **SQLite3** | Lightweight, file-based SQL engine for inventory data. |
| **Libraries** | `sounddevice`, `numpy`, `RPi.GPIO` | Audio IO and Hardware Control. |
| **NLP Utilities** | `num2words`, `rapidfuzz` | Number normalization ("60" vs "sixty") and fuzzy matching. |
