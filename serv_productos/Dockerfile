# Usamos PHP en su versión de consola
FROM php:8.1-cli

# Instalamos las dependencias necesarias de Linux para compilar el driver de PostgreSQL
RUN apt-get update && apt-get install -y libpq-dev \
    && docker-php-ext-install pdo pdo_pgsql

# Directorio de trabajo
WORKDIR /app

# Copiamos el código fuente de PHP
COPY . .

# Exponemos el puerto
EXPOSE 8001

# Arrancamos el servidor interno de PHP
CMD ["php", "-S", "0.0.0.0:8001", "serv_productos_doc.php"]