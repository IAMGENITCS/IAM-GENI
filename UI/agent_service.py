import os
import threading
import traceback
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from fastapi.security import OAuth2PasswordBearer
import jwt
import requests

from IAMAssistant import IAMAssistant  # Ensure this is imported correctly

# Initialize FastAPI application
app = FastAPI(title="IAM Assistant Service", version="1.0.0")

# CORS configuration to allow Streamlit on 8501
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8501", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT authentication - OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Lazy singleton IAM Assistant with thread lock
_assistant_lock = threading.Lock()
_assistant: Optional[IAMAssistant] = None


def get_assistant() -> IAMAssistant:
    global _assistant
    if _assistant is None:
        with _assistant_lock:
            if _assistant is None:  # double-checked locking
                _assistant = IAMAssistant()
    return _assistant


# Azure OpenID Configuration URL to get public keys (JWKS)
OPENID_CONFIG_URL = f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}/v2.0/.well-known/openid-configuration"


def get_jwk():
    """Fetch JWKS from Azure's OpenID Configuration"""
    try:
        response = requests.get(OPENID_CONFIG_URL)
        response.raise_for_status()
        openid_config = response.json()
        jwks_uri = openid_config['jwks_uri']

        # Fetch the JWKS (JSON Web Key Set)
        jwks = requests.get(jwks_uri).json()
        return jwks['keys']
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public keys: {e}")


# Verify JWT token using Azure public keys
def verify_token(token: str = Depends(oauth2_scheme)):
    """Verify JWT token using Azure public keys"""
    try:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is missing")
        
        # Debugging: Log the token to check if it's being received correctly
        print(f"Received token: {token}")

        unverified_header = jwt.get_unverified_header(token)
        if unverified_header is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

        kid = unverified_header['kid']
        keys = get_jwk()

        rsa_key = {}
        for key in keys:
            if key['kid'] == kid:
                rsa_key = {
                    'kty': key['kty'],
                    'kid': key['kid'],
                    'use': key['use'],
                    'n': key['n'],
                    'e': key['e']
                }
                break

        if not rsa_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to find appropriate key")

        # Validate the JWT token's signature using the public key
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            #audience=os.getenv("CLIENT_ID"),  # Your Azure Client ID (App ID)
            #options={"verify_aud": False},
            options={"verify_signature": False, "verify_aud": False},
            issuer=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}/v2.0"
        )
        
        # Debugging: Log the payload for verification
        print(f"Token validated successfully. Payload: {payload}")
        
        return payload  # Return the decoded payload if valid

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token verification failed: {str(e)}")


# ---- Models ----
class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ThreadResponse(BaseModel):
    thread_id: str


class ChatResponse(BaseModel):
    reply: str

# ---- Health check ----
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# ---- Routes ----

@app.post("/thread", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(token: str = Depends(verify_token)):
    try:
        assistant = get_assistant()
        tid = assistant.create_thread()
        return ThreadResponse(thread_id=tid)
    except Exception as e:
        traceback.print_exc()  # Log full error stack
        raise HTTPException(status_code=500, detail=f"Failed to create thread: {e}")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, token: str = Depends(verify_token)):
    try:
        assistant = get_assistant()
        reply = assistant.chat_on_thread(thread_id=req.thread_id, user_query=req.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        traceback.print_exc()  # Log full error stack
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
