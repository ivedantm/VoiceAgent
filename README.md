# AI Voice Agent for the Blind

> 🚧 **Work in Progress** — This project is actively being developed.

## Overview

An Alexa-style AI voice assistant designed for the blind. Activated by voice, it listens to user input and translates responses to Braille.

Built with [LiveKit](https://livekit.io/) and Python.

---

## Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd <your-repo-name>

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env.local
```

## Environment Variables

See `.env.example` for required variables.

---

## Usage

```bash
python agent.py
```

---

## Status

- [ ] Voice activation
- [ ] Voice input processing
- [ ] Braille translation
- [ ] More coming soon...

---

## License

TBD
