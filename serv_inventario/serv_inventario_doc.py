import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Departamento de Inventario",
    description="Servicio encargado de la custodia y control de existencias físicas de productos. \n\n" \
                "Este servicio actúa como el punto central de integración para la validación de stock en los procesos de venta y gestión de pedidos. \n\n" \
                "Ejecutar en puerto **8003** y asegurarse de que los servicios de Pedidos (8002), Productos (8001) y Auth (8004) estén activos.",
    version="2.0.0",
    contact={
        "name": "Espinoza Benítez Josué Said, Alumno de SOA - TecNM Querétaro",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONEXIÓN A POSTGRESQL (RENDER) ---
DB_URL = "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"

def get_db_connection():
    """Establece la conexión a la base de datos en Render."""
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# --- SEGURIDAD: CONEXIÓN AL SERVICIO DE AUTH ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8004/token")

def obtener_usuario_actual(token: str = Depends(oauth2_scheme)):
    """Valida el token comunicándose con el Microservicio de Auth (8004)."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get("http://auth:8004/verify", headers=headers)
        res.raise_for_status()
        return res.json()["usuario"]
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=401, 
            detail="Acceso denegado: Token inválido o Servicio de Autenticación (8004) apagado."
        )

# --- MODELOS DE DATOS (CONTRATOS SWAGGER) ---
class Inventario(BaseModel):
    id_producto: int = Field(..., example=1, description="ID del producto en el catálogo oficial")
    stock: int = Field(..., ge=0, example=50, description="Cantidad física disponible")

class InventarioOperacion(BaseModel):
    id_producto: int = Field(..., example=1, description="ID del producto a operar")
    cantidad: int = Field(..., gt=0, example=5, description="Cantidad a descontar o agregar")

class InventarioUpdate(BaseModel):
    stock: int = Field(..., ge=0, example=25, description="Nueva cantidad total disponible en almacén")

# --- ENDPOINTS V1 (Públicos/Internos) ---

@app.get(
    "/inventario",
    response_model=List[Inventario],
    tags=["Consultas"],
    summary="Obtener inventario completo ordenado",
    status_code=status.HTTP_200_OK
)
def obtener_inventario_completo():
    """
    **Retorna el estado actual de todas las existencias.**
    
    Lee la base de datos persistente y devuelve la lista de
    todos los productos con su respectivo stock físico.
    Incluye ordenamiento ascendente por ID de producto (ORDER BY id_producto ASC).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_producto, cantidad AS stock FROM inventario ORDER BY id_producto ASC")
    items = cur.fetchall()
    conn.close()
    return [dict(i) for i in items]

@app.post(
    "/inventario",
    tags=["Operaciones"],
    summary="Registrar nuevo producto en inventario",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "El producto ya tiene inventario asignado"},
        404: {"description": "El producto no existe en el catálogo oficial (Puerto 8001)"},
        503: {"description": "El servicio de Productos no está disponible"}
    }
)
def registrar_inventario(nuevo: Inventario):
    """
    **Da de alta un producto en el almacén físico.**
    
    Valida conectándose al servicio de Productos (8001) que el ID realmente exista en el catálogo antes de asignarle stock inicial.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id_producto FROM inventario WHERE id_producto = %s", (nuevo.id_producto,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="El producto ya tiene un registro de inventario inicializado.")
    
    try:
        headers_seguros = {"Authorization": "Bearer token_seguro_said"}
        res_productos = requests.get("http://productos:8001/v2/productos", headers=headers_seguros)
        if res_productos.status_code != 200:
            raise HTTPException(status_code=503, detail="El servicio de Productos no responde.")
            
        catalogo = res_productos.json()
        if not any(int(p['id_producto']) == nuevo.id_producto for p in catalogo):
            raise HTTPException(status_code=404, detail=f"El producto con ID {nuevo.id_producto} no existe en el catálogo.")
            
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="El servicio de Productos (8001) está apagado.")

    cur.execute(
        "INSERT INTO inventario (id_producto, cantidad) VALUES (%s, %s)",
        (nuevo.id_producto, nuevo.stock)
    )
    conn.commit()
    conn.close()
    return {"mensaje": "Inventario inicializado correctamente", "datos": nuevo}

@app.post("/inventario/descontar", tags=["Operaciones"], summary="Descontar stock de inventario")
def descontar_stock(operacion: InventarioOperacion):
    """Reduce las existencias físicas tras una venta. Se ejecuta de forma síncrona desde el Orquestador. Valida: Inv >= Pedido."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM inventario WHERE id_producto = %s", (operacion.id_producto,))
    stock = cur.fetchone()
    
    if not stock:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no existe en el inventario")
    if stock['cantidad'] < operacion.cantidad:
        conn.close()
        raise HTTPException(status_code=400, detail="Stock insuficiente. Venta rechazada.")
        
    cur.execute("UPDATE inventario SET cantidad = cantidad - %s WHERE id_producto = %s RETURNING cantidad", (operacion.cantidad, operacion.id_producto))
    nuevo_stock = cur.fetchone()['cantidad']
    conn.commit()
    conn.close()
    return {"mensaje": "Stock descontado exitosamente", "nuevo_stock": nuevo_stock}

@app.post("/inventario/agregar", tags=["Operaciones"], summary="Agregar stock al inventario")
def agregar_stock(operacion: InventarioOperacion):
    """Incrementa las existencias físicas (Reabastecimiento de mercancía)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM inventario WHERE id_producto = %s", (operacion.id_producto,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no existe en el inventario")
        
    cur.execute("UPDATE inventario SET cantidad = cantidad + %s WHERE id_producto = %s RETURNING cantidad", (operacion.cantidad, operacion.id_producto))
    nuevo_stock = cur.fetchone()['cantidad']
    conn.commit()
    conn.close()
    return {"mensaje": "Stock agregado exitosamente", "nuevo_stock": nuevo_stock}


# --- ENDPOINTS V2 (Seguros con JWT) ---

@app.patch(
    "/v2/inventario/{id_producto}",
    tags=["Versión 2 (Segura)"],
    summary="Ajustar stock forzado (Requiere Token)",
    responses={
        200: {"description": "Stock actualizado exitosamente"},
        404: {"description": "El producto no tiene registro de inventario"}
    }
)
def actualizar_stock_v2(id_producto: int, update: InventarioUpdate, usuario: str = Depends(obtener_usuario_actual)):
    """
    **Ajuste de Stock a nivel Administrativo.** A diferencia de descontar/agregar, este endpoint sobrescribe la cantidad total
    exacta en el almacén (ej. por auditoría física o merma).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "UPDATE inventario SET cantidad = %s WHERE id_producto = %s RETURNING id_producto",
        (update.stock, id_producto)
    )
    actualizado = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    if not actualizado:
        raise HTTPException(status_code=404, detail="No existe un registro de inventario para este producto")
        
    return {"mensaje": "Stock actualizado exitosamente", "status": "success"}

@app.delete(
    "/v2/inventario/{id_producto}",
    tags=["Versión 2 (Segura)"],
    summary="Eliminar registro de almacén (Requiere Token)",
    responses={
        200: {"description": "Registro de inventario eliminado permanentemente"},
        404: {"description": "El producto no tiene registro de inventario"}
    }
)
def eliminar_inventario_v2(id_producto: int, usuario: str = Depends(obtener_usuario_actual)):
    """
    **Baja definitiva del almacén.**
    Borra por completo la fila del producto en la tabla de inventario.
    Se usa cuando un producto ya no se venderá ni se almacenará jamás.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM inventario WHERE id_producto = %s RETURNING id_producto", (id_producto,))
    eliminado = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    if not eliminado:
        raise HTTPException(status_code=404, detail="Registro de inventario no encontrado")
        
    return {"mensaje": "Registro de inventario eliminado permanentemente", "status": "success"}