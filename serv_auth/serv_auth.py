from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI(
    title="Servicio de Identidad (Auth)",
    description="Microservicio centralizado para emisión y validación de Tokens.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite que el frontend de Astro se conecte
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Base de datos de usuarios (Próximamente en MySQL)
USUARIOS_DB = {
    "said": "admin",
    "profe": "admin"
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token", tags=["Emisión"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Recibe credenciales y emite un Token de acceso."""
    usuario_db = USUARIOS_DB.get(form_data.username)
    
    if not usuario_db or usuario_db != form_data.password:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    
    return {
        "access_token": f"token_seguro_{form_data.username}", 
        "token_type": "bearer"
    }

@app.get("/verify", tags=["Validación"])
def verify_token(token: str = Depends(oauth2_scheme)):
    """Los otros microservicios consumirán esta ruta para comprobar si un token es válido."""
    if not token.startswith("token_seguro_"):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    
    usuario_extraido = token.replace("token_seguro_", "")
    return {"valido": True, "usuario": usuario_extraido}

# uvicorn serv_auth_doc:app --port 8004 --reload