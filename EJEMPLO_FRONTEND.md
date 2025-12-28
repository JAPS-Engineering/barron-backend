# Ejemplo de Uso del Endpoint desde el Frontend

## Endpoint
```
POST http://localhost:8000/api/schedule
```

## Estructura del Request Body

### Campos Requeridos:
- `orders`: Array de órdenes de trabajo
- `machines`: Objeto con las máquinas disponibles

### Campos Opcionales (con valores por defecto):
- `setup_times`: Tiempos de setup entre formatos
- `horizonte_aprovechamiento`: 12 horas (por defecto)
- `costo_inventario_unitario`: 0.002 (por defecto)
- `default_setup_time`: 1.5 horas (por defecto)
- `start_datetime`: Fecha/hora de inicio (opcional, usa fecha actual si no se envía)
- `work_hours_per_day`: 24.0 (por defecto, producción 24/7)
- `work_start_hour`: 0 (por defecto)
- `work_days`: [0,1,2,3,4,5,6] (por defecto, todos los días)

## 🆕 Nuevo Formato: OTs con Múltiples Productos (Modelo Optimizado)

El nuevo modelo permite que cada OT requiera múltiples productos. El algoritmo agrupa productos del mismo tipo para minimizar setups y respeta las fechas límite de todas las OTs.

### Ejemplo Completo con Datos de Testeo Optimizados

```javascript
// Datos de testeo con OTs de múltiples productos
const datosTesteoOptimizado = {
  orders: [
    {
      id: "OT0",
      due: 12,
      cluster: 5,
      products: { A: 100, B: 200 }  // OT0 requiere productos A y B
    },
    {
      id: "OT1",
      due: 18,
      cluster: 4,
      products: { B: 150 }  // OT1 solo requiere producto B
    },
    {
      id: "OT2",
      due: 20,
      cluster: 3,
      products: { A: 50, B: 100 }  // OT2 requiere productos A y B
    },
    {
      id: "OT3",
      due: 25,
      cluster: 2,
      products: { C: 200 }  // OT3 solo requiere producto C
    },
    {
      id: "OT4",
      due: 30,
      cluster: 4,
      products: { A: 80, C: 120 }  // OT4 requiere productos A y C
    },
  ],
  machines: {
    Linea_1: { capacity: 120, available_at: 0, last_format: null },
    Linea_2: { capacity: 90, available_at: 0, last_format: null },
  },
  setup_times: {
    "A-B": 1.5,
    "B-A": 1.5,
    "A-C": 2.0,
    "C-A": 2.0,
    "B-C": 1.0,
    "C-B": 1.0,
  },
  horizonte_aprovechamiento: 12,
  costo_inventario_unitario: 0.002,
  default_setup_time: 1.5,
  start_datetime: "2024-01-25T08:00:00", // Jueves 25 de enero de 2024 a las 8 AM
  work_hours_per_day: 24.0, // Producción 24/7
  work_start_hour: 0,
  work_days: [0, 1, 2, 3, 4, 5, 6], // Todos los días
};

// Función para obtener los logs
async function fetchScheduleLogs() {
  try {
    const response = await fetch('http://localhost:8000/api/schedule', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(datosTesteoOptimizado),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Schedule API Error:', errorData);
      throw new Error(`Error: ${JSON.stringify(errorData)} (Status: ${response.status})`);
    }

    const resultado = await response.json();
    
    // Los logs están en resultado.logs (array de strings)
    return resultado.logs;
    
  } catch (error) {
    console.error('Error fetching schedule logs:', error);
    throw error;
  }
}

// Uso de la función
fetchScheduleLogs()
  .then(logs => {
    // logs es un array de strings, cada string es una línea
    logs.forEach(line => {
      console.log(line);
      // O agregar a tu componente de consola
    });
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

## Formato Antiguo (Compatibilidad)

Si tus OTs tienen un solo producto, puedes usar el formato antiguo:

```javascript
const datosTesteoAntiguo = {
  orders: [
    { id: "OT1001", due: 12, qty: 800, cluster: 5, format: "A" },
    { id: "OT1002", due: 18, qty: 500, cluster: 4, format: "B" },
    // ...
  ],
  machines: {
    Linea_1: { capacity: 120, available_at: 0, last_format: null },
    Linea_2: { capacity: 90, available_at: 0, last_format: null },
  },
  // ... resto de parámetros
};
```

## Estructura de la Respuesta

### Con Modelo Optimizado (múltiples productos)

```json
{
  "schedule": [
    {
      "type": "SETUP",
      "machine": "Linea_1",
      "start": 0.0,
      "end": 1.5,
      "duration": 1.5,
      "format": "B",
      "color": "#808080"
    },
    {
      "type": "PRODUCTION",
      "machine": "Linea_1",
      "start": 1.5,
      "end": 5.25,
      "duration": 3.75,
      "product": "B",
      "quantity": 450,
      "format": "B",
      "ot_ids": ["OT0", "OT1", "OT2"],
      "color": "#4A90E2",
      "on_time": true,
      "start_datetime_str": "9:30 AM jueves 25",
      "end_datetime_str": "1:15 PM jueves 25"
    },
    {
      "type": "SETUP",
      "machine": "Linea_1",
      "start": 5.25,
      "end": 6.75,
      "duration": 1.5,
      "format": "A",
      "color": "#808080"
    },
    {
      "type": "PRODUCTION",
      "machine": "Linea_1",
      "start": 6.75,
      "end": 7.67,
      "duration": 0.92,
      "product": "A",
      "quantity": 230,
      "format": "A",
      "ot_ids": ["OT0", "OT2", "OT4"],
      "color": "#4A90E2",
      "on_time": true,
      "start_datetime_str": "2:45 PM jueves 25",
      "end_datetime_str": "3:40 PM jueves 25"
    }
  ],
  "schedule_by_machine": {
    "Linea_1": [...],
    "Linea_2": [...]
  },
  "summary": {
    "total_ots": 5,
    "total_setups": 4,
    "total_horas": 12.5,
    "qty_total_cliente": 1000,
    "qty_total_extra": 0,
    "atrasos": [],
    "horizonte_usado": 0
  },
  "logs": [
    "============================================================",
    "PROGRAMA DE PRODUCCIÓN GENERADO",
    "============================================================",
    "",
    "🔧 [Linea_1] SETUP",
    "   ⏱️  0.00h → 1.50h",
    "   🏷️  Cambio a: B",
    "",
    "📦 [Linea_1] Producción: B",
    "   ⏱️  1.50h → 5.25h",
    "   📊 Cantidad: 450 unidades",
    "   📋 OTs beneficiadas: OT0, OT1, OT2",
    "   ✅ A TIEMPO",
    ...
  ]
}
```

### Con Formato Antiguo (un solo producto por OT)

```json
{
  "schedule": [
    {
      "type": "OT",
      "machine": "Linea_1",
      "start": 0.0,
      "end": 6.67,
      "duration": 6.67,
      "id": "OT1001",
      "due": 12.0,
      "qty_cliente": 800,
      "qty_extra": 0,
      "format": "A",
      "color": "#4A90E2",
      "on_time": true,
      "start_datetime_str": "8 AM jueves 25",
      "end_datetime_str": "2:40 PM jueves 25"
    }
  ],
  ...
}
```

## Ejemplo Mínimo (solo campos requeridos)

### Con múltiples productos:
```javascript
const datosMinimos = {
  orders: [
    {
      id: "OT0",
      due: 12,
      cluster: 5,
      products: { A: 100, B: 200 }
    }
  ],
  machines: {
    Linea_1: { capacity: 120, available_at: 0, last_format: null }
  }
};

const response = await fetch('http://localhost:8000/api/schedule', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(datosMinimos),
});

const resultado = await response.json();
console.log(resultado.logs); // Array de strings con los logs
```

### Con formato antiguo:
```javascript
const datosMinimos = {
  orders: [
    { id: "OT1001", due: 12, qty: 800, cluster: 5, format: "A" }
  ],
  machines: {
    Linea_1: { capacity: 120, available_at: 0, last_format: null }
  }
};
```

## Explicación de los Campos

### Orders (Órdenes de Trabajo)

#### Nuevo Formato (múltiples productos):
- `id`: Identificador único de la OT (string)
- `due`: Fecha compromiso en horas desde ahora (número)
- `cluster`: Prioridad comercial, mayor = más importante (número entero)
- `products`: **Diccionario de productos y cantidades** (objeto)
  - Ejemplo: `{"A": 100, "B": 200}` significa que la OT requiere 100 unidades de A y 200 de B

#### Formato Antiguo (compatibilidad):
- `id`: Identificador único de la OT (string)
- `due`: Fecha compromiso en horas desde ahora (número)
- `qty`: Cantidad solicitada por el cliente (número entero)
- `cluster`: Prioridad comercial, mayor = más importante (número entero)
- `format`: Formato/producto único (string)

### Machines (Máquinas)
- `capacity`: Unidades producidas por hora (número)
- `available_at`: Reloj interno de la máquina en horas (número, por defecto 0)
- `last_format`: Último formato producido (string o null)

### Setup Times (Opcional)
- Formato: `"PRODUCTO1-PRODUCTO2": tiempo_en_horas`
- Ejemplo: `"A-B": 1.5` significa que cambiar de producto A a B toma 1.5 horas

## Campos de la Respuesta

### ScheduleItem (Nuevo Formato - PRODUCTION)
- `type`: "PRODUCTION" o "SETUP"
- `machine`: Nombre de la máquina
- `start`: Hora de inicio en horas
- `end`: Hora de fin en horas
- `duration`: Duración en horas
- `product`: Producto producido (string)
- `quantity`: Cantidad total producida (número)
- `ot_ids`: Array de IDs de OTs que se benefician de esta producción
- `format`: Producto (compatibilidad)
- `on_time`: Si todas las OTs relacionadas están a tiempo (boolean)
- `start_datetime_str`: Fecha/hora de inicio formateada
- `end_datetime_str`: Fecha/hora de fin formateada

### ScheduleItem (Formato Antiguo - OT)
- `type`: "OT" o "SETUP"
- `id`: ID de la OT
- `due`: Fecha compromiso
- `qty_cliente`: Cantidad para cliente
- `qty_extra`: Cantidad extra producida
- `format`: Formato/producto
- `on_time`: Si la OT está a tiempo

## Manejo de Errores

El endpoint puede devolver:
- **422 Unprocessable Entity**: El body no cumple con la validación (falta algún campo requerido o tiene formato incorrecto)
- **500 Internal Server Error**: Error al procesar el programa
  - Si el problema no es factible (no se pueden completar todas las OTs a tiempo), el error incluirá detalles

Siempre verifica `response.ok` antes de procesar la respuesta.

## Ventajas del Nuevo Modelo

1. **Agrupación Inteligente**: Agrupa todos los productos del mismo tipo para minimizar setups
2. **Minimiza Makespan**: Reduce el tiempo total de producción
3. **Respeta Fechas Límite**: Garantiza que todas las OTs se completen a tiempo (restricción hard)
4. **Flexible**: Funciona con cualquier cantidad de productos

## Ejemplo de Visualización en React

```javascript
import { fetchScheduleLogs, datosTesteoOptimizado } from './ejemplo_useProductionData';

function ProductionConsole() {
  const [logs, setLogs] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const handleLoadLogs = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const resultado = await fetchScheduleLogs(true);
      setLogs(resultado.logs);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleLoadLogs} disabled={loading}>
        {loading ? 'Cargando...' : 'Ver Logs de Producción'}
      </button>
      
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}
      
      <div style={{ 
        fontFamily: 'monospace', 
        whiteSpace: 'pre-wrap',
        backgroundColor: '#1e1e1e',
        color: '#d4d4d4',
        padding: '1rem',
        borderRadius: '4px',
        maxHeight: '500px',
        overflow: 'auto'
      }}>
        {logs.map((line, index) => (
          <div key={index}>{line}</div>
        ))}
      </div>
    </div>
  );
}
```
