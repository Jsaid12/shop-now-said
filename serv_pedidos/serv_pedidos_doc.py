"""
===============================================================================
MICROSERVICIO DE PEDIDOS (ORQUESTADOR ASÍNCRONO) - ARQUITECTURA SOA
===============================================================================
Autor: Espinoza Benítez Josué Said
Puerto asignado: 8002
"""
from fastapi.middleware.cors import CORSMiddleware
import requests
import pika
import json
import threading
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="Departamento de Pedidos (Orquestador Asíncrono)",
    description="Este servicio actúa como el Director de Orquesta. Valida la interacción entre Órdenes, Clientes y Productos utilizando RabbitMQ como bus de mensajería.\n\n"
                "**Demuestra el patrón de Simulación de Caos**: Si el inventario falla o no hay stock físico, el pedido no se pierde, se encapsula en una tabla de auditoría de pendientes.",
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
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# --- SEGURIDAD: CONEXIÓN AL SERVICIO DE AUTH ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="https://shopnow-auth.onrender.com/token")

def obtener_usuario_actual(token: str = Depends(oauth2_scheme)):
    """Valida el token comunicándose con el Microservicio de Auth (8004)."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get("https://shopnow-auth.onrender.com/verify", headers=headers)
        res.raise_for_status()
        return res.json()["usuario"]
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=401, detail="Token inválido o Auth (8004) apagado.")

# --- MODELOS DE DATOS (CONTRATOS SWAGGER) ---
class PedidoRegistro(BaseModel):
    id_cliente: int = Field(..., example=1, description="ID del cliente comprador en el padrón")
    id_producto: int = Field(..., example=1, description="ID del producto a comprar en el catálogo")
    cantidad: int = Field(..., gt=0, example=2, description="Cantidad de unidades a comprar")

class PedidoRespuesta(BaseModel):
    id_pedido: int = Field(..., example=101, description="ID Autoincremental del pedido")
    id_cliente: int = Field(..., example=1, description="Cliente orquestado")
    id_producto: int = Field(..., example=1, description="Producto orquestado")
    cantidad: int = Field(..., example=2)
    total: float = Field(..., example=500.50, description="Total pagado")
    estado: str = Field(..., example="Completado", description="Estado de la transacción")

class PedidoPendienteRespuesta(BaseModel):
    id_cliente: int = Field(..., example=1)
    id_producto: int = Field(..., example=1)
    cantidad: int = Field(..., example=2)
    motivo: str = Field(..., example="Stock insuficiente", description="Razón por la que se retuvo la orden")

# =============================================================================
# WORKER ASÍNCRONO (EL CONSUMIDOR DE RABBITMQ)
# =============================================================================
def trabajador_asincrono():
    credentials = pika.PlainCredentials('shopnow', '5h0pn0w')
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq', credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue='cola_pedidos', durable=True)
    except Exception as e:
        print(f"[!] Error crítico: No se pudo conectar a RabbitMQ. {e}")
        return

    def procesar_mensaje(ch, method, properties, body):
        pedido = json.loads(body.decode())
        print(f"\n[*] RabbitMQ -> Procesando interacción (Órdenes a Clientes y Productos): {pedido}")
        
        try:
            headers_seguros = {"Authorization": "Bearer token_seguro_said"}
            
            # 1. Validar Cliente (8000)
            res_cliente = requests.get("https://shopnow-clientes-v714.onrender.com/v2/clientes", headers=headers_seguros)
            res_cliente.raise_for_status()
            if not any(int(c['id_cliente']) == pedido['id_cliente'] for c in res_cliente.json()):
                print(f"[X] Cliente {pedido['id_cliente']} no existe. Descartando.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 2. Validar Producto (8001)
            res_producto = requests.get("https://shopnow-productos-e2tb.onrender.com/v2/productos", headers=headers_seguros)
            res_producto.raise_for_status()
            producto = next((p for p in res_producto.json() if int(p['id_producto']) == pedido['id_producto']), None)
            if not producto:
                print(f"[X] Producto {pedido['id_producto']} no existe. Descartando.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            precio_unitario = float(producto['precio'])
            total_pagar = precio_unitario * pedido['cantidad']

            # 3. Descontar Inventario (8003)
            payload_inv = {"id_producto": pedido['id_producto'], "cantidad": pedido['cantidad']}
            res_inventario = requests.post("https://shopnow-inventario-5x4i.onrender.com/inventario/descontar", json=payload_inv)
            
            conn = get_db_connection()
            cur = conn.cursor()

            # --- SIMULACIÓN DE CAOS: Falta de Stock ---
            if res_inventario.status_code == 400:
                print(f"[X] Stock insuficiente. Enviando a tabla de pedidos pendientes.")
                cur.execute(
                    "INSERT INTO pedidos_pendientes (id_cliente, id_producto, cantidad, motivo, encolado_en) VALUES (%s, %s, %s, %s, %s)",
                    (pedido['id_cliente'], pedido['id_producto'], pedido['cantidad'], "Stock insuficiente", datetime.now())
                )
                conn.commit()
                conn.close()
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
                
            res_inventario.raise_for_status()

            # 4. Éxito: Guardar Venta
            cur.execute(
                "INSERT INTO pedidos (id_cliente, id_producto, cantidad, precio_unitario, total, estado, fecha_pedido) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_pedido",
                (pedido['id_cliente'], pedido['id_producto'], pedido['cantidad'], precio_unitario, total_pagar, 'Completado', datetime.now())
            )
            conn.commit()
            conn.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except requests.exceptions.RequestException as e:
            print(f"[!] Falla de red: Reencolando mensaje... {e}")
            time.sleep(5)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='cola_pedidos', on_message_callback=procesar_mensaje, auto_ack=False)
    channel.start_consuming()

@app.on_event("startup")
def arrancar_worker():
    threading.Thread(target=trabajador_asincrono, daemon=True).start()

# =============================================================================
# ENDPOINTS REST (PRODUCTOR Y CONSULTAS)
# =============================================================================

@app.get(
    "/v2/pedidos", 
    response_model=List[PedidoRespuesta],
    tags=["Versión 2 (Segura) - Consultas"], 
    summary="Obtener historial de pedidos exitosos (Requiere Token)",
    responses={200: {"description": "Lista de ventas procesadas exitosamente"}}
)
def obtener_pedidos(usuario: str = Depends(obtener_usuario_actual)):
    """Retorna la bitácora histórica de ventas completadas desde PostgreSQL."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_pedido, id_cliente, id_producto, cantidad, total, estado FROM pedidos ORDER BY id_pedido DESC")
    pedidos = cur.fetchall()
    conn.close()
    return [dict(p) for p in pedidos]

@app.get(
    "/v2/pedidos/pendientes", 
    response_model=List[PedidoPendienteRespuesta],
    tags=["Versión 2 (Segura) - Consultas"], 
    summary="Obtener pedidos fallidos por caos (Requiere Token)",
    responses={200: {"description": "Lista de pedidos retenidos por falta de inventario"}}
)
def obtener_pedidos_pendientes(usuario: str = Depends(obtener_usuario_actual)):
    """Consulta la tabla de `pedidos_pendientes` para auditar ventas no concretadas."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_cliente, id_producto, cantidad, motivo FROM pedidos_pendientes ORDER BY encolado_en DESC")
    pendientes = cur.fetchall()
    conn.close()
    return [dict(p) for p in pendientes]

@app.post(
    "/v2/pedidos", 
    status_code=status.HTTP_202_ACCEPTED, 
    tags=["Versión 2 (Segura) - Operaciones"],
    summary="Encolar un nuevo pedido en RabbitMQ (Requiere Token)",
    responses={
        202: {"description": "Pedido recibido y depositado en el bus de mensajería (RabbitMQ)"},
        503: {"description": "Servicio de RabbitMQ inoperativo"}
    }
)
def encolar_pedido(nuevo: PedidoRegistro, usuario: str = Depends(obtener_usuario_actual)):
    """
    **Punto de entrada asíncrono.** No guarda en la base de datos inmediatamente.
    El Orquestador tomará este mensaje de la cola, validará contra los demás microservicios
    (Clientes, Productos e Inventario) y guardará el resultado de forma transparente.
    """
    try:
        credentials = pika.PlainCredentials('shopnow', '5h0pn0w')
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq', credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue='cola_pedidos', durable=True)
        channel.basic_publish(
            exchange='', 
            routing_key='cola_pedidos', 
            body=nuevo.json(), 
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        return {"estado": "Encolado", "mensaje": "Pedido depositado en la cola asíncrona."}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"RabbitMQ caído: {e}")

@app.delete(
    "/v2/pedidos/{id_pedido}", 
    tags=["Versión 2 (Segura) - Operaciones"], 
    summary="Cancelar pedido (Requiere Token)",
    responses={
        200: {"description": "Estado del pedido actualizado a 'Cancelado'"},
        404: {"description": "Pedido no encontrado"}
    }
)
def cancelar_pedido(id_pedido: int, usuario: str = Depends(obtener_usuario_actual)):
    """Actualiza el estado de un pedido completado a 'Cancelado'."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pedidos SET estado = 'Cancelado' WHERE id_pedido = %s RETURNING id_pedido", (id_pedido,))
    cancelado = cur.fetchone()
    conn.commit()
    conn.close()
    if not cancelado:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return {"mensaje": "Pedido cancelado exitosamente"}