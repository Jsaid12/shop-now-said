# Usamos una versión ligera de Python
FROM python:3.10-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos e instalamos las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código fuente
COPY . .

# Exponemos el puerto de este servicio (CAMBIAR SEGÚN EL SERVICIO)
EXPOSE 8000

# Comando para ejecutar (CAMBIAR EL NOMBRE DEL ARCHIVO Y EL PUERTO)
CMD ["uvicorn", "serv_clientes_doc:app", "--host", "0.0.0.0", "--port", "8000"]