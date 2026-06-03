import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Departamento de Clientes",
    description="Servicio encargado de la custodia y registro oficial de los clientes de la empresa. \n\n" \
    "Este servicio actúa como el punto central de integración para la validación de clientes en los procesos de venta y atención al cliente. \n\n" \
    "Ejecutar en puerto **8000** y asegurarse de que los servicios de Pedidos (8002) y Productos (8001) estén activos para su correcto funcionamiento.",
    version="2.0.0",
    contact={
        "name": "Espinoza Benítez Josué Said, Alumno de SOA - TecNM Querétaro",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite que el frontend de Astro se conecte
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONEXIÓN A POSTGRESQL (RENDER) ---
DB_URL = "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"

def get_db_connection():
    """Establece la conexión a la base de datos en Render."""
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# --- CONEXIÓN AL SERVICIO DE AUTH CENTRALIZADO ---

# ¡Magia pura! Le decimos a Swagger que el botón verde "Authorize" 
# debe pedirle el token al puerto 8004, no a este servidor.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8004/token")

def obtener_usuario_actual(token: str = Depends(oauth2_scheme)):
    """
    Toma el token que manda el usuario y le pregunta al 
    Microservicio de Auth (8004) si es válido.
    """
    try:
        headers = {"Authorization": f"Bearer {token}"}
        # Hacemos una petición rápida al puerto 8004 para validar
        res = requests.get("http://auth:8004/verify", headers=headers)
        res.raise_for_status()
        
        datos_auth = res.json()
        return datos_auth["usuario"]
        
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=401, 
            detail="Acceso denegado: Token inválido o Servicio de Autenticación (8004) apagado."
        )
# --- FIN CONEXIÓN AUTH ---

class Cliente(BaseModel):
    id_cliente: int = Field(..., example=101, description="ID numérico único") # type: ignore
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: EmailStr = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., example="555-1234") # type: ignore
    activo: bool = Field(..., example=True, description="Indica si el cliente está activo o inactivo") # type: ignore

class ClienteRegistro(BaseModel):
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: EmailStr = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., example="555-1234") # type: ignore

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3, example="Juan Pérez") # type: ignore
    correo: Optional[EmailStr] = Field(None, example="juan@ejemplo.com") # type: ignore
    direccion: Optional[str] = Field(None, example="Calle 123") # type: ignore
    telefono: Optional[str] = Field(None, example="555-1234") # type: ignore


@app.get(
    "/clientes",
    response_model=List[Cliente],
    tags=["Consultas"],
    summary="Obtener lista de clientes",
    status_code=200,
    responses={
        200: {
            "description": "Lista de clientes obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_cliente": 101,
                            "nombre": "Juan Pérez",
                            "correo": "juan@ejemplo.com",
                            "direccion": "Calle 123",
                            "telefono": "555-1234"
                        }
                    ]
                }
            }
        }
    }
)
def obtener_clientes(estado: Optional[str] = None):
    """Retorna el padrón oficial de clientes desde la Base de Datos.
    
    Este endpoint obtiene la lista completa de todos los clientes registrados
    en la base de datos persistente (PostgreSQL).
    
    Returns:
        List[Cliente]: Lista de clientes con todos sus datos.
    
    Puedes filtrar enviando un query param `?estado=inactivo` para obtener solo los clientes inactivos, 
    o `?estado=todos` para obtener absolutamente todos los registros sin importar su estado.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    if estado == "inactivo":
        cur.execute("SELECT * FROM clientes WHERE activo = FALSE")
    elif estado == "todos":
        cur.execute("SELECT * FROM clientes")
    else:
        cur.execute("SELECT * FROM clientes WHERE activo = TRUE")
        
    clientes = cur.fetchall()
    conn.close()
    return [dict(c) for c in clientes]

@app.get(
    "/v2/clientes", 
    response_model=List[Cliente],
    tags=["Versión 2 (Segura)"],
    summary="Obtener lista de clientes (Requiere Token)",
    responses={
        200: {
            "description": "Lista de clientes obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_cliente": 101,
                            "nombre": "Juan Pérez",
                            "correo": "juan@ejemplo.com",
                            "direccion": "Calle 123",
                            "telefono": "555-1234"
                        }
                    ]
                }
            }
        }
    }
)
def obtener_clientes_v2(estado: Optional[str] = None, usuario: str = Depends(obtener_usuario_actual)): # <-- Candado agregado aquí
    """Retorna el padrón oficial de clientes desde la Base de Datos.
    
    Este endpoint obtiene la lista completa de todos los clientes registrados
    en la base de datos persistente (PostgreSQL).
    
    Returns:
        List[Cliente]: Lista de clientes con todos sus datos.
    
    Puedes filtrar enviando un query param `?estado=inactivo` para obtener solo los clientes inactivos, 
    o `?estado=todos` para obtener absolutamente todos los registros sin importar su estado.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    if estado == "inactivo":
        cur.execute("SELECT * FROM clientes WHERE activo = FALSE")
    elif estado == "todos":
        cur.execute("SELECT * FROM clientes")
    else:
        cur.execute("SELECT * FROM clientes WHERE activo = TRUE")
        
    clientes = cur.fetchall()
    conn.close()
    return [dict(c) for c in clientes]

@app.post(
    "/v2/clientes",
    tags=["Versión 2 (Segura)"],
    summary="Registrar nuevo cliente",
    status_code=201,
    responses={
        201: {
            "description": "Cliente registrado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente registrado en la base de datos",
                        "id_cliente": 101,
                        "status": "success"
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def registrar_cliente(nuevo: ClienteRegistro, usuario: str = Depends(obtener_usuario_actual)):
    """Registra un nuevo cliente en la base de datos.
    
    Crea un nuevo cliente con el siguiente flujo:
    1. Valida los datos de entrada según el modelo ClienteRegistro
    2. Genera un ID único autoincremental en PostgreSQL
    3. Almacena el cliente en la tabla
    
    Args:
        nuevo (ClienteRegistro): Datos del cliente a registrar.
            - nombre: Nombre del cliente (mínimo 3 caracteres)
            - correo: Email válido del cliente
            - direccion: Dirección del cliente
            - telefono: Teléfono de contacto
    
    Returns:
        dict: Diccionario con mensaje de éxito e ID asignado del cliente.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        INSERT INTO clientes (nombre, correo, direccion, telefono, activo, fecha_registro) 
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_cliente;
        """,
        (nuevo.nombre, nuevo.correo, nuevo.direccion, nuevo.telefono, True, date.today())
    )
    nuevo_id = cur.fetchone()['id_cliente']
    conn.commit()
    conn.close()
    
    return {"mensaje": "Cliente registrado en la base de datos", "id_cliente": nuevo_id, "status": "success"}

@app.delete(
    "/v2/clientes/{id_cliente}", # <-- Cambiado a v2
    tags=["Versión 2 (Segura)"],
    summary="Eliminar cliente (Requiere Token)",
    status_code=200,
    responses={
        200: {"description": "Cliente eliminado exitosamente"},
        404: {"description": "Cliente no encontrado con el ID especificado"}
    }
)
def eliminar_cliente_soft(id_cliente: int, usuario: str = Depends(obtener_usuario_actual)): # <-- Candado de seguridad agregado
    """Desactiva un cliente existente de la base de datos.
    
    Busca y desactiva un cliente por su ID único, marcando su registro
    como inactivo en la base de datos persistente.
    
    Args:
        id_cliente (int): ID único del cliente a desactivar.
    
    Returns:
        dict: Diccionario con mensaje de confirmación de desactivación.
    
    Raises:
        HTTPException: Con status 404 si el cliente no existe.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("UPDATE clientes SET activo = FALSE WHERE id_cliente = %s RETURNING id_cliente", (id_cliente,))
    eliminado = cur.fetchone()
    conn.commit()
    conn.close()
    
    if not eliminado:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    return {"mensaje": "Cliente desactivado exitosamente", "status": "success"}

@app.patch(
    "/v2/clientes/{id_cliente}", # <-- Cambiado a v2
    tags=["Versión 2 (Segura)"],
    summary="Actualizar cliente parcialmente (Requiere Token)",
    status_code=200,
    responses={
        200: {
            "description": "Cliente actualizado parcialmente de forma exitosa",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente actualizado parcialmente exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Cliente no encontrado con el ID especificado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cliente no encontrado"
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def actualizar_cliente_parcial(id_cliente: int, update: ClienteUpdate, usuario: str = Depends(obtener_usuario_actual)): # <-- Candado de seguridad agregado
    """Actualiza parcialmente un cliente existente.
    
    Permite actualizar uno o más campos de un cliente sin necesidad
    de proporcionar todos los datos. Los campos no proporcionados
    se mantienen sin cambios en la base de datos.
    
    Args:
        id_cliente (int): ID único del cliente a actualizar.
        update (ClienteUpdate): Datos opcionales a actualizar.
            - nombre (opcional): Nuevo nombre (mínimo 3 caracteres)
            - correo (opcional): Nuevo email válido
            - direccion (opcional): Nueva dirección
            - telefono (opcional): Nuevo teléfono de contacto
    
    Returns:
        dict: Diccionario con mensaje de confirmación de actualización.
    
    Raises:
        HTTPException: Con status 404 si el cliente no existe.
    """
    campos_a_actualizar = []
    valores = []
    
    # Tu excelente lógica dinámica se mantiene intacta
    if update.nombre is not None:
        campos_a_actualizar.append("nombre = %s")
        valores.append(update.nombre)
    if update.correo is not None:
        campos_a_actualizar.append("correo = %s")
        valores.append(update.correo)
    if update.direccion is not None:
        campos_a_actualizar.append("direccion = %s")
        valores.append(update.direccion)
    if update.telefono is not None:
        campos_a_actualizar.append("telefono = %s")
        valores.append(update.telefono)
        
    if not campos_a_actualizar:
        return {"mensaje": "No se proporcionaron datos para actualizar", "status": "success"}
        
    valores.append(id_cliente)
    query_sql = f"UPDATE clientes SET {', '.join(campos_a_actualizar)} WHERE id_cliente = %s RETURNING id_cliente"
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query_sql, tuple(valores))
    actualizado = cur.fetchone()
    conn.commit()
    conn.close()
    
    if not actualizado:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    return {"mensaje": "Cliente actualizado exitosamente", "status": "success"}
