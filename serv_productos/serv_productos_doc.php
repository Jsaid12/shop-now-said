<?php
/**
 * ============================================================================
 * MICROSERVICIO DE PRODUCTOS (v2) - ARQUITECTURA SOA
 * ============================================================================
 * Autor: Espinoza Benítez Josué Said
 * Lenguaje: PHP Puro (Sin frameworks)
 * Puerto asignado: 8001
 * * @OA\Info(
 * title="Departamento de Productos",
 * version="2.0.0",
 * description="Servicio encargado de la gestión del catálogo de productos en base de datos (PostgreSQL). Actúa como proveedor de validación para los procesos de venta y control de inventario.",
 * @OA\Contact(
 * name="Espinoza Benítez Josué Said, Alumno de SOA - TecNM Querétaro"
 * )
 * )
 * * @OA\SecurityScheme(
 * securityScheme="bearerAuth",
 * type="http",
 * scheme="bearer",
 * bearerFormat="JWT",
 * description="Introduce el token proporcionado por el microservicio de Auth (Puerto 8004)"
 * )
 * ============================================================================
 */

// 1. CONFIGURACIÓN DE CABECERAS CORS (A PRUEBA DE BALAS)
header("Content-Type: application/json; charset=UTF-8");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, DELETE, PATCH, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With");

// 2. INTERCEPTOR DE PREFLIGHT (OPTIONS CORS)
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit(0);
}

/**
 * @OA\Schema(
 * schema="Producto",
 * title="Esquema de Producto",
 * description="Modelo de datos que representa un producto en el catálogo persistido en PostgreSQL",
 * type="object",
 * required={"id_producto", "descripcion", "precio", "activo"},
 * @OA\Property(property="id_producto", type="integer", example=1, description="ID autoincremental"),
 * @OA\Property(property="descripcion", type="string", example="Laptop Gamer RTX 4050", description="Nombre descriptivo"),
 * @OA\Property(property="precio", type="number", format="float", example=15000.50, description="Precio unitario"),
 * @OA\Property(property="activo", type="boolean", example=true, description="Estado de disponibilidad")
 * )
 */

/**
 * ============================================================================
 * CAPA DE SEGURIDAD
 * ============================================================================
 */
function validarAutenticacion() {
    $authHeader = '';
    
    // Leemos el token de forma segura, compatible con el servidor interno de Docker
    if (isset($_SERVER['HTTP_AUTHORIZATION'])) {
        $authHeader = $_SERVER['HTTP_AUTHORIZATION'];
    } elseif (isset($_SERVER['REDIRECT_HTTP_AUTHORIZATION'])) {
        $authHeader = $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
    }

    // Validamos que exista un token Bearer (ya sea el de pruebas o el JWT real de Astro)
    if (empty($authHeader) || strpos($authHeader, 'Bearer') === false) {
        http_response_code(401);
        echo json_encode(["detail" => "Token inválido o ausente. No tienes permiso."]);
        exit();
    }
}

/**
 * ============================================================================
 * CAPA DE ACCESO A DATOS (POSTGRESQL RENDER)
 * ============================================================================
 */
$host = 'dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com';
$db   = 'shopnow_663n';
$user = 'shopnow_663n_user';
$pass = 'mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl';

$dsn = "pgsql:host=$host;port=5432;dbname=$db;";
$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
];

try {
     $pdo = new PDO($dsn, $user, $pass, $options);
} catch (\PDOException $e) {
     http_response_code(500);
     echo json_encode(["detail" => "Error de conexión a la BD PostgreSQL: " . $e->getMessage()]);
     exit();
}

/**
 * ============================================================================
 * ENRUTADOR PRINCIPAL
 * ============================================================================
 */
$method = $_SERVER['REQUEST_METHOD'];
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

$inputJSON = file_get_contents('php://input');
$body = json_decode($inputJSON, true);

/**
 * @OA\Get(
 * path="/v2/productos",
 * summary="Obtener catálogo de productos",
 * description="Retorna la lista completa de productos activos consultando directamente la base de datos PostgreSQL. Requiere token de autorización.",
 * tags={"Consultas"},
 * security={{"bearerAuth":{}}},
 * @OA\Response(
 * response=200,
 * description="Lista de productos obtenida exitosamente",
 * @OA\JsonContent(type="array", @OA\Items(ref="#/components/schemas/Producto"))
 * ),
 * @OA\Response(
 * response=401,
 * description="Acceso denegado: Token ausente o inválido"
 * )
 * )
 */
if ($method === 'GET' && ($uri === '/v2/productos' || $uri === '/productos')) {
    validarAutenticacion();
    $stmt = $pdo->query("SELECT id_producto, descripcion, precio, activo FROM productos WHERE activo = TRUE ORDER BY id_producto ASC");
    $productos = $stmt->fetchAll();
    
    $productos_formateados = array_map(function($p) {
        return [
            "id_producto" => (int)$p['id_producto'],
            "descripcion" => $p['descripcion'],
            "precio" => (float)$p['precio'],
            "activo" => (bool)$p['activo']
        ];
    }, $productos);
    
    http_response_code(200);
    echo json_encode($productos_formateados);
    exit();
}

/**
 * @OA\Post(
 * path="/v2/productos",
 * summary="Registrar nuevo producto",
 * description="Crea un nuevo registro de producto insertándolo en la tabla de PostgreSQL. Valida los datos obligatorios y devuelve el ID generado.",
 * tags={"Operaciones"},
 * security={{"bearerAuth":{}}},
 * @OA\RequestBody(
 * required=true,
 * description="Datos del nuevo producto a registrar",
 * @OA\JsonContent(
 * required={"descripcion","precio"},
 * @OA\Property(property="descripcion", type="string", example="Mouse Inalámbrico Logitech"),
 * @OA\Property(property="precio", type="number", format="float", example=250.00)
 * )
 * ),
 * @OA\Response(
 * response=201,
 * description="Producto registrado exitosamente en BD"
 * ),
 * @OA\Response(
 * response=422,
 * description="Datos de entrada inválidos o formato incorrecto (Faltan campos)"
 * )
 * )
 */
elseif ($method === 'POST' && $uri === '/v2/productos') {
    validarAutenticacion();
    if (!isset($body['descripcion']) || !isset($body['precio'])) {
        http_response_code(422);
        echo json_encode(["detail" => "Faltan campos obligatorios"]);
        exit();
    }
    $stmt = $pdo->prepare("INSERT INTO productos (descripcion, precio, activo) VALUES (?, ?, TRUE) RETURNING id_producto");
    $stmt->execute([$body['descripcion'], $body['precio']]);
    $resultado = $stmt->fetch();
    
    http_response_code(201);
    echo json_encode(["mensaje" => "Producto creado", "id_producto" => $resultado['id_producto']]);
    exit();
}

// --- RUTA: PATCH /v2/productos/{id} ---
elseif ($method === 'PATCH' && preg_match('/^\/v2\/productos\/(\d+)$/', $uri, $matches)) {
    validarAutenticacion();
    $id = $matches[1];
    if (!isset($body['descripcion']) || !isset($body['precio'])) {
        http_response_code(422);
        echo json_encode(["detail" => "Faltan campos para actualizar"]);
        exit();
    }
    $stmt = $pdo->prepare("UPDATE productos SET descripcion = ?, precio = ? WHERE id_producto = ?");
    $stmt->execute([$body['descripcion'], $body['precio'], $id]);
    
    http_response_code(200);
    echo json_encode(["mensaje" => "Producto actualizado exitosamente"]);
    exit();
}

// --- RUTA: DELETE /v2/productos/{id} ---
elseif ($method === 'DELETE' && preg_match('/^\/v2\/productos\/(\d+)$/', $uri, $matches)) {
    validarAutenticacion();
    $id = $matches[1];
    // Soft Delete: Solo lo desactivamos para no romper el historial de pedidos
    $stmt = $pdo->prepare("UPDATE productos SET activo = FALSE WHERE id_producto = ?");
    $stmt->execute([$id]);
    
    http_response_code(200);
    echo json_encode(["mensaje" => "Producto dado de baja del catálogo"]);
    exit();
}

/**
 * @OA\Response(
 * response="default",
 * description="Endpoint no encontrado en el enrutador PHP"
 * )
 */
// --- RUTA: 404 ---
else {
    http_response_code(404);
    echo json_encode(["detail" => "Endpoint no encontrado"]);
    exit();
}