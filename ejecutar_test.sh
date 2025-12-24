#!/bin/bash
# Script para ejecutar el test de la API
# Uso: ./ejecutar_test.sh

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Error: No se encontró el entorno virtual"
    echo "💡 Ejecuta primero: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Ejecutar el test
python3 test_api.py

