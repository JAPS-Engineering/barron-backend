# API de Programación de Producción - Barron Backend

API REST para programación heurística de producción usando FastAPI.

## Instalación

1. Crear un entorno virtual (recomendado):
```bash
python3 -m venv venv
source venv/bin/activate  # En Windows/WSL: venv\Scripts\activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecutar el servidor:
```bash
python3 app.py
```

O usando uvicorn directamente:
```bash
python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

## Documentación Interactiva

Una vez que el servidor esté corriendo, puedes acceder a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints

### POST /schedule

Endpoint principal que recibe las órdenes de trabajo y máquinas, y devuelve el programa de producción optimizado.

**Request Body:**

```json
{
  "orders": [
    {
      "id": "OT1001",
      "due": 12,
      "qty": 800,
      "cluster": 5,
      "format": "A"
    }
  ],
  "machines": {
    "Linea_1": {
      "capacity": 120,
      "available_at": 0,
      "last_format": null
    }
  },
  "setup_times": {
    "A-B": 1.5,
    "B-A": 1.5,
    "A-C": 2.0,
    "C-A": 2.0
  },
  "horizonte_aprovechamiento": 12,
  "costo_inventario_unitario": 0.002,
  "default_setup_time": 1.5
}
```

**Response:**

```json
{
  "schedule": [
    {
      "type": "SETUP",
      "machine": "Linea_1",
      "start": 0.0,
      "end": 1.5
    },
    {
      "type": "OT",
      "id": "OT1001",
      "machine": "Linea_1",
      "start": 1.5,
      "end": 8.17,
      "due": 12.0,
      "qty_cliente": 800,
      "qty_extra": 350,
      "format": "A"
    }
  ],
  "summary": {
    "total_ots": 7,
    "total_setups": 4,
    "total_horas": 45.23,
    "qty_total_cliente": 6200,
    "qty_total_extra": 1100,
    "atrasos": [],
    "horizonte_usado": 12
  }
}
```

### GET /

Endpoint raíz con información de la API.

### GET /health

Endpoint de salud para verificar que la API está funcionando.

## Ejemplo de Uso desde Python

Ver archivo `ejemplo_uso_api.py` para un ejemplo completo.

```python
import requests

response = requests.post(
    "http://localhost:8000/schedule",
    json={
        "orders": [...],
        "machines": {...},
        # ... otros parámetros
    }
)

resultado = response.json()
```

## Ejemplo de Uso desde JavaScript/TypeScript (Frontend)

```javascript
const response = await fetch('http://localhost:8000/schedule', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    orders: [
      { id: "OT1001", due: 12, qty: 800, cluster: 5, format: "A" }
    ],
    machines: {
      "Linea_1": { capacity: 120, available_at: 0, last_format: null }
    },
    setup_times: {
      "A-B": 1.5,
      "B-A": 1.5
    }
  })
});

const resultado = await response.json();
console.log(resultado);
```

## Parámetros Opcionales

Los siguientes parámetros tienen valores por defecto y son opcionales:

- `setup_times`: Si no se proporciona, se usará `default_setup_time` para todos los cambios de formato
- `horizonte_aprovechamiento`: Por defecto 12 horas
- `costo_inventario_unitario`: Por defecto 0.002
- `default_setup_time`: Por defecto 1.5 horas

## Notas

- El algoritmo ordena las OT por prioridad calculada como `due / cluster`
- Se produce cantidad extra cuando conviene aprovechar el rollo (dentro del horizonte y si el ahorro de setup supera el costo de inventario)
- Los tiempos de setup se especifican en formato string: `"A-B"` para cambiar de formato A a formato B

