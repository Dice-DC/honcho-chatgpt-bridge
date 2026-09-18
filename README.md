# Honcho ↔ ChatGPT Bridge

A deliberately small FastAPI service that lets a private Custom GPT share Honcho
memory with Hermes.

## Identity mapping

| Purpose | Value |
|---|---|
| Honcho workspace | `hermes` |
| Human peer | `Norm` |
| Hermes AI peer | `Elara` |
| ChatGPT AI peer | `ChatGPT` |
| ChatGPT session | `chatgpt` |

The human peer stays the same across integrations. The AI peers stay separate so
Honcho can preserve provenance.

## What the bridge exposes

- `POST /recall` — ask Honcho what it knows about `Norm`.
- `POST /record` — record a user or ChatGPT message into the `chatgpt` session.
- `GET /health` — non-secret configuration health check.

`/recall` and `/record` require:

```text
Authorization: Bearer <BRIDGE_API_KEY>
```

The Honcho API key remains only on the server and is never placed inside the
Custom GPT instructions or Action schema.

## Local setup

Create a virtual environment with Python 3.11+ and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On this Mac, the known-good Python is:

```bash
/Users/norm/.hermes/hermes-agent/venv/bin/python3.11 -m venv .venv
```

Copy the environment template:

```bash
cp .env.example .env
```

Generate a bridge secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put that value into `BRIDGE_API_KEY` and put your Honcho API key into
`HONCHO_API_KEY`.

Export the values before starting the server:

```bash
set -a
source .env
set +a

uvicorn app:app --reload --port 8000
```

Then test:

```bash
curl http://127.0.0.1:8000/health
```

Recall:

```bash
curl -X POST http://127.0.0.1:8000/recall \
  -H "Authorization: Bearer $BRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"What stable preferences should an assistant know about Norm?"}'
```

Record:

```bash
curl -X POST http://127.0.0.1:8000/record \
  -H "Authorization: Bearer $BRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"role":"user","content":"I prefer concise technical explanations."}'
```

## Deploy

The included `Dockerfile` works on most container hosts. `render.yaml` is also
included for a simple Render deployment.

Set these secrets in the hosting provider, not in Git:

- `HONCHO_API_KEY`
- `BRIDGE_API_KEY`

And these non-secret values:

- `HONCHO_WORKSPACE=hermes`
- `HONCHO_USER_PEER=Norm`
- `HONCHO_AI_PEER=ChatGPT`
- `HONCHO_SESSION=chatgpt`
- `PUBLIC_BASE_URL=https://YOUR-BRIDGE.example.com`

After deployment your bridge should have an HTTPS origin. Set `PUBLIC_BASE_URL` to that exact origin, for example:

```text
https://YOUR-BRIDGE.example.com
```

## Configure the Custom GPT Action

FastAPI automatically serves an OpenAPI document at:

```text
https://YOUR-BRIDGE.example.com/openapi.json
```

In the Custom GPT builder:

1. Add an Action.
2. Import the schema from `/openapi.json`, or paste the generated schema.
3. Set authentication to API key / Bearer authentication.
4. Use the value of `BRIDGE_API_KEY` as the secret.
5. Paste the contents of `gpt-instructions.txt` into the GPT instructions.

Do **not** put `HONCHO_API_KEY` into ChatGPT.

## Why separate sessions?

Hermes currently uses a global session strategy. ChatGPT uses its own
`chatgpt` session, but both integrations share the human peer `Norm`.
Honcho's peer-level reasoning can synthesize information across the sessions
associated with that peer while preserving which assistant produced each turn.

## Honcho latency note

Honcho reasons about newly written messages asynchronously. A message can be
accepted successfully by `/record` before that information is reflected in a
later synthesized `peer.chat()` response.

## Security notes

- The bridge exposes only recall and record rather than the complete Honcho API.
- The Honcho key never leaves the bridge host.
- The bridge has an independent secret so it can be rotated without rotating
  Honcho credentials.
- Keep the bridge private to your GPT; do not publish the bearer token.
- Do not commit `.env`.
