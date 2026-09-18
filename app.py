import os
import secrets
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from honcho import Honcho


APP_TITLE = "Honcho ChatGPT Bridge"
APP_VERSION = "1.0.0"

HONCHO_API_KEY = os.environ["HONCHO_API_KEY"]
HONCHO_WORKSPACE = os.getenv("HONCHO_WORKSPACE", "hermes")
HONCHO_USER_PEER = os.getenv("HONCHO_USER_PEER", "Norm")
HONCHO_AI_PEER = os.getenv("HONCHO_AI_PEER", "ChatGPT")
HONCHO_SESSION = os.getenv("HONCHO_SESSION", "chatgpt")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
BRIDGE_API_KEY = os.environ["BRIDGE_API_KEY"]

honcho = Honcho(
    workspace_id=HONCHO_WORKSPACE,
    api_key=HONCHO_API_KEY,
)

user_peer = honcho.peer(HONCHO_USER_PEER)
ai_peer = honcho.peer(HONCHO_AI_PEER)
session = honcho.session(HONCHO_SESSION)

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=(
        "A minimal authenticated bridge that lets a private ChatGPT Action "
        "read and write memory for one Honcho user peer."
    ),
    servers=([{"url": PUBLIC_BASE_URL}] if PUBLIC_BASE_URL else None),
)


bearer_scheme = HTTPBearer(auto_error=False)


def require_bridge_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )

    supplied = credentials.credentials.strip()
    if not secrets.compare_digest(supplied, BRIDGE_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Bearer token.",
        )


class RecallRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description=(
            "A focused question about what ChatGPT should know about Norm "
            "before answering the current request."
        ),
    )


class RecallResponse(BaseModel):
    memory: str
    workspace: str
    user_peer: str


class RecordRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=20000)


class RecordResponse(BaseModel):
    ok: bool
    role: str
    session: str
    note: str


class HealthResponse(BaseModel):
    ok: bool
    workspace: str
    user_peer: str
    ai_peer: str
    session: str


@app.get(
    "/health",
    response_model=HealthResponse,
    operation_id="healthCheck",
)
def health() -> HealthResponse:
    # Deliberately does not expose secrets.
    return HealthResponse(
        ok=True,
        workspace=HONCHO_WORKSPACE,
        user_peer=HONCHO_USER_PEER,
        ai_peer=HONCHO_AI_PEER,
        session=HONCHO_SESSION,
    )


@app.post(
    "/recall",
    response_model=RecallResponse,
    dependencies=[Depends(require_bridge_key)],
    operation_id="recallMemory",
)
def recall_memory(body: RecallRequest) -> RecallResponse:
    prompt = (
        "You are supplying memory to ChatGPT about the human peer "
        f"{HONCHO_USER_PEER}. Answer only with relevant, grounded information "
        "from this peer's Honcho memory. If the memory does not support an "
        "answer, say that clearly. Do not invent facts.\n\n"
        f"ChatGPT needs to know:\n{body.query}"
    )

    answer = user_peer.chat(prompt)

    return RecallResponse(
        memory=str(answer),
        workspace=HONCHO_WORKSPACE,
        user_peer=HONCHO_USER_PEER,
    )


@app.post(
    "/record",
    response_model=RecordResponse,
    dependencies=[Depends(require_bridge_key)],
    operation_id="recordMemory",
)
def record_memory(body: RecordRequest) -> RecordResponse:
    peer = user_peer if body.role == "user" else ai_peer
    session.add_messages([peer.message(body.content)])

    return RecordResponse(
        ok=True,
        role=body.role,
        session=HONCHO_SESSION,
        note=(
            "Message accepted by Honcho. Synthesized reasoning may update "
            "asynchronously."
        ),
    )
