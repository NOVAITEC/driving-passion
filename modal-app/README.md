# Driving Passion - Modal Deployment

Auto Import Marge Calculator op Modal.

## Quick Start

```bash
# Install Modal CLI
pip install modal

# Login
modal setup

# Create secrets
modal secret create apify-secret APIFY_TOKEN=your_token
modal secret create openrouter-secret OPENROUTER_API_KEY=your_key

# Deploy
cd modal-app
modal deploy app.py
```

## Endpoints

- `POST /analyze` - Analyze a German car listing
- `GET /health` - Health check
- `POST /bpm` - Calculate BPM only

## API URL

After deployment:
```
https://novaitec--driving-passion-analyze.modal.run
```
