FROM python:3.11-slim

# Instalar SQLite y otras dependencias del sistema
RUN apt-get update && apt-get install -y \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código
COPY . .

# Crear directorio para media
RUN mkdir -p media/images

# Exponer puerto
EXPOSE 5000

# Comando para ejecutar
CMD ["python", "bot_server.py"]
