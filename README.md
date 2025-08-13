# Ember Log 🔥📜

Ember Log is a Python-based backend service that monitors a folder for new Phoenix Fire Department dispatch audio files, transcribes them into JSON, and appends them to a master ledger for easy querying and analysis.

## ✨ Features

- **Directory Watcher** – Automatically detects new `.wav` files in your inbox directory.
- **Transcription Engine** – Uses Faster-Whisper or other pluggable backends for accurate speech-to-text.
- **JSON Output** – Each transcription saved to its own JSON file.
- **Ledger Support** – Appends structured data to a master JSON ledger for aggregation.
- **Extensible** – Modular OOP design to swap transcription engines or add new output sinks (e.g., database, API, cloud storage).

## 📂 Project Structure (planned)

```
emberlog/
├── emberlog/
│   ├── config.py         # Paths, constants, env vars
│   ├── watcher.py        # Watches inbox dir, queues new files
│   ├── queue_manager.py  # Queue handling
│   ├── transcriber/      # Multiple transcription engine backends
│   ├── parser.py         # Extract structured incident data
│   ├── ledger.py         # Append to master ledger
│   └── utils/            # Logging, file ops, helpers
└── tests/
```

## ⚡ Getting Started

**1. Clone the repo**

```bash
git clone https://github.com/jcrawford2000/emberlog.git
cd emberlog
```

**2. Install dependencies with Poetry**

```bash
poetry install
```

**3. Run the watcher**

```bash
poetry run python -m emberlog.watcher
```

## 🛡 License

### Personal and Non-Commercial Use

You may use, copy, modify, and share Ember Log for **personal or non-commercial purposes** for free.

- **Non-commercial** means you are not selling, licensing, or offering services that include or depend on Ember Log for profit.
- You must include this credit in any copies or modifications:

```
Based on Ember Log, originally created by Justin Crawford (https://github.com/jcrawford2000/emberlog)
```

### Commercial Use

If you wish to use Ember Log **commercially**, you must obtain a **commercial license** from the author.
This includes:

- Selling it as part of a product or service.
- Using it in a business setting where it supports revenue-generating activities.

**Contact for commercial licensing**: `justin.crawford@tech-harbor.us`

### No Warranty

This software is provided “as-is,” without warranties of any kind. The author is not liable for any damages from its use.

---

**TL;DR**

- ✅ Free for personal/hobby use (with credit)
- 💰 Commercial use requires a paid license
- ❌ Removing attribution is not allowed

---
