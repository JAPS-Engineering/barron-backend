#!/bin/bash
# Script para iniciar el servidor de la API
# Uso: ./iniciar_servidor.sh

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Entorno virtual activado"
else
    echo "⚠️  No se encontró el entorno virtual. Creando uno..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Instalando dependencias..."
    pip install -r requirements.txt
fi

# Iniciar el servidor
echo "🚀 Iniciando servidor en http://localhost:8000"
echo "📚 Documentación disponible en http://localhost:8000/docs"
echo ""
python3 app.py

