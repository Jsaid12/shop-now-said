// src/lib/api.ts

const AUTH_URL = 'http://127.0.0.1:8004';
const CLIE_URL = 'http://127.0.0.1:8000';
const PROD_URL = 'http://127.0.0.1:8001';
const PEDI_URL = 'http://127.0.0.1:8002';
const INVE_URL = 'http://127.0.0.1:8003';

// ── MANEJO DEL TOKEN Y SESIÓN ──────────────────────────────────────────
export function setToken(token: string, username: string) {
  localStorage.setItem('soa_token', token);
  localStorage.setItem('soa_user', username);
}
export function clearToken() { 
  localStorage.removeItem('soa_token'); 
  localStorage.removeItem('soa_user'); 
}
export function getToken(): string | null { 
  return localStorage.getItem('soa_token'); 
}
export function getUsername(): string { 
  return localStorage.getItem('soa_user') || 'Usuario'; 
}
export function isLoggedIn(): boolean { 
  return !!getToken(); 
}
function getHeaders() {
  return { 
    'Content-Type': 'application/json', 
    'Authorization': `Bearer ${getToken()}` 
  };
}

// ── MICROSERVICIO AUTH (8004) ──────────────────────────────────────────
export async function login(username: string, password: string): Promise<void> {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  
  const res = await fetch(`${AUTH_URL}/token`, { 
    method: 'POST', 
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData 
  });
  if (!res.ok) throw new Error('Credenciales inválidas');
  const data = await res.json();
  setToken(data.access_token, username);
}

// ── MICROSERVICIO PRODUCTOS (8001 - PHP) ───────────────────────────────
export async function getProductos(): Promise<any[]> {
  const res = await fetch(`${PROD_URL}/v2/productos`, { headers: getHeaders() });
  if (res.status === 401) { clearToken(); window.location.replace('/'); throw new Error('Sesión expirada'); }
  return res.ok ? res.json() : [];
}
export async function crearProducto(descripcion: string, precio: number) {
  const res = await fetch(`${PROD_URL}/v2/productos`, { method: 'POST', headers: getHeaders(), body: JSON.stringify({ descripcion, precio }) });
  if (!res.ok) throw new Error('Error al crear producto');
  return res.json();
}
export async function updateProducto(id: number, descripcion: string, precio: number) {
  const res = await fetch(`${PROD_URL}/v2/productos/${id}`, { method: 'PATCH', headers: getHeaders(), body: JSON.stringify({ descripcion, precio }) });
  if (!res.ok) throw new Error('Error al actualizar producto');
  return res.json();
}
export async function deleteProducto(id: number) {
  const res = await fetch(`${PROD_URL}/v2/productos/${id}`, { method: 'DELETE', headers: getHeaders() });
  if (!res.ok) throw new Error('Error al eliminar producto');
  return res.json();
}

// ── MICROSERVICIO CLIENTES (8000 - Python) ─────────────────────────────
export async function getClientes(): Promise<any[]> {
  const res = await fetch(`${CLIE_URL}/v2/clientes`, { headers: getHeaders() });
  return res.ok ? res.json() : [];
}
export async function crearCliente(nombre: string, correo: string) {
  const payload = { nombre, correo, direccion: "Conocido", telefono: "0000000000" };
  const res = await fetch(`${CLIE_URL}/v2/clientes`, { method: 'POST', headers: getHeaders(), body: JSON.stringify(payload) });
  if (!res.ok) throw new Error('Error al registrar cliente');
  return res.json();
}
export async function updateCliente(id: number, nombre: string, correo: string) {
  const res = await fetch(`${CLIE_URL}/v2/clientes/${id}`, { method: 'PATCH', headers: getHeaders(), body: JSON.stringify({ nombre, correo }) });
  if (!res.ok) throw new Error('Error al actualizar cliente');
  return res.json();
}
export async function deleteCliente(id: number) {
  const res = await fetch(`${CLIE_URL}/v2/clientes/${id}`, { method: 'DELETE', headers: getHeaders() });
  if (!res.ok) throw new Error('Error al eliminar cliente');
  return res.json();
}

// ── MICROSERVICIO INVENTARIO (8003 - Python) ───────────────────────────
export async function getInventario(): Promise<any[]> {
  const res = await fetch(`${INVE_URL}/inventario`); 
  return res.ok ? res.json() : [];
}
export async function initInventario(id_producto: number, stock: number) {
  const res = await fetch(`${INVE_URL}/inventario`, { method: 'POST', headers: getHeaders(), body: JSON.stringify({ id_producto, stock }) });
  if (!res.ok) throw new Error('Error al inicializar inventario');
  return res.json();
}
export async function updateInventario(id_producto: number, stock: number) {
  const res = await fetch(`${INVE_URL}/v2/inventario/${id_producto}`, { method: 'PATCH', headers: getHeaders(), body: JSON.stringify({ stock }) });
  if (!res.ok) throw new Error('Error al actualizar inventario');
  return res.json();
}
export async function deleteInventario(id_producto: number) {
  const res = await fetch(`${INVE_URL}/v2/inventario/${id_producto}`, { method: 'DELETE', headers: getHeaders() });
  if (!res.ok) throw new Error('Error al eliminar inventario');
  return res.json();
}

// ── ORQUESTADOR DE PEDIDOS (8002 - Python + RabbitMQ) ──────────────────
export async function getPedidos(): Promise<any[]> {
  const res = await fetch(`${PEDI_URL}/v2/pedidos`, { headers: getHeaders() });
  return res.ok ? res.json() : [];
}
export async function getPedidosPendientes(): Promise<any[]> {
  const res = await fetch(`${PEDI_URL}/v2/pedidos/pendientes`, { headers: getHeaders() });
  return res.ok ? res.json() : [];
}
export async function crearPedido(payload: { id_cliente: number, id_producto: number, cantidad: number }) {
  const res = await fetch(`${PEDI_URL}/v2/pedidos`, { method: 'POST', headers: getHeaders(), body: JSON.stringify(payload) });
  if (!res.ok) throw new Error('Error al encolar pedido');
  return res.json();
}
export async function cancelarPedido(id_pedido: number) {
  const res = await fetch(`${PEDI_URL}/v2/pedidos/${id_pedido}`, { method: 'DELETE', headers: getHeaders() });
  if (!res.ok) throw new Error('Error al cancelar pedido');
  return res.json();
}