@echo off
color 0A
echo ===================================================
echo   SISTEMA SHOPNOW SOA - INICIO AUTOMATIZADO
echo ===================================================
echo.

echo [1/5] Iniciando RabbitMQ en Docker...
docker compose up -d
echo Esperando 10 segundos para que RabbitMQ arranque por completo...
timeout /t 10 /nobreak > NUL

echo [2/5] Levantando Servicio de Clientes (Puerto 8000 - Python)...
start "CLIENTES (8000)" cmd /k "title CLIENTES (8000) && uvicorn serv_clientes_doc:app --port 8000 --reload"

echo [3/5] Levantando Servicio de Productos (Puerto 8001 - PHP)...
start "PRODUCTOS PHP (8001)" cmd /k "title PRODUCTOS PHP (8001) && php -S localhost:8001 serv_productos_doc.php"

echo [4/5] Levantando Servicio de Inventario (Puerto 8003 - Python)...
start "INVENTARIO (8003)" cmd /k "title INVENTARIO (8003) && uvicorn serv_inventario_doc:app --port 8003 --reload"

echo [5/5] Levantando Orquestador de Pedidos (Puerto 8002 - Python + RabbitMQ)...
start "PEDIDOS (8002)" cmd /k "title PEDIDOS (8002) && uvicorn serv_pedidos_doc:app --port 8002 --reload"

echo.
echo ===================================================
echo   ¡TODOS LOS SERVICIOS ESTAN EN LINEA!
echo   RabbitMQ Panel: http://localhost:15672
echo ===================================================
pause