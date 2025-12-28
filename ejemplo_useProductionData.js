/**
 * Ejemplo de cómo usar el endpoint /api/schedule desde el frontend
 * 
 * Este archivo muestra cómo implementar fetchScheduleLogs correctamente
 * con los datos de testeo optimizados que usamos en el backend.
 * 
 * 🆕 NUEVO: Soporte para OTs con múltiples productos (modelo optimizado)
 */

// =====================================================
// DATOS DE TESTEO OPTIMIZADOS (múltiples productos)
// =====================================================
// Fechas límite ajustadas para ser realistas considerando makespan ~73 horas
export const datosTesteoOptimizado = {
  orders: [
    // Día 1 - OTs urgentes con múltiples productos (completadas en ~16h)
    { id: "OT0", due: 20, cluster: 5, products: { A: 200, B: 300 } },
    { id: "OT1", due: 20, cluster: 4, products: { B: 250, C: 150 } },
    { id: "OT2", due: 20, cluster: 3, products: { A: 180, B: 200 } },
    { id: "OT3", due: 20, cluster: 2, products: { C: 400 } },
    { id: "OT4", due: 20, cluster: 4, products: { A: 150, C: 200 } },
    // Día 2-3 - OTs intermedias (completadas en ~36h)
    { id: "OT5", due: 40, cluster: 1, products: { A: 500, B: 300 } },
    { id: "OT6", due: 60, cluster: 2, products: { C: 350, B: 200 } },
    { id: "OT7", due: 60, cluster: 5, products: { B: 400 } },
    { id: "OT8", due: 60, cluster: 3, products: { A: 250, B: 150, C: 100 } },
    { id: "OT9", due: 60, cluster: 4, products: { C: 450 } },
    // Día 4-5 - OTs con más tiempo (completadas en ~55h)
    { id: "OT10", due: 80, cluster: 2, products: { B: 300, A: 200 } },
    { id: "OT11", due: 80, cluster: 5, products: { A: 600, B: 400 } },
    { id: "OT12", due: 80, cluster: 3, products: { C: 250, A: 150 } },
    { id: "OT13", due: 80, cluster: 4, products: { A: 400, C: 300 } },
    { id: "OT14", due: 80, cluster: 1, products: { B: 350 } },
    // Día 6-7 - OTs con tiempo suficiente (completadas en ~73h)
    { id: "OT15", due: 100, cluster: 5, products: { C: 500, B: 200 } },
    { id: "OT16", due: 100, cluster: 2, products: { A: 400 } },
    { id: "OT17", due: 100, cluster: 3, products: { B: 250, C: 150 } },
    { id: "OT18", due: 100, cluster: 4, products: { C: 550, A: 300 } },
    { id: "OT19", due: 100, cluster: 1, products: { A: 350, B: 250 } },
    // Más OTs para llenar el calendario (completadas en ~73h)
    { id: "OT20", due: 100, cluster: 5, products: { B: 450, A: 200 } },
    { id: "OT21", due: 100, cluster: 2, products: { A: 300, C: 250 } },
    { id: "OT22", due: 100, cluster: 3, products: { C: 500 } },
    { id: "OT23", due: 100, cluster: 4, products: { B: 380, A: 220 } },
    { id: "OT24", due: 100, cluster: 1, products: { A: 450, B: 300, C: 200 } },
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

// =====================================================
// DATOS DE TESTEO FORMATO ANTIGUO (compatibilidad)
// =====================================================
export const datosTesteoAntiguo = {
  orders: [
    { id: "OT1001", due: 12, qty: 800, cluster: 5, format: "A" },
    { id: "OT1002", due: 18, qty: 500, cluster: 4, format: "B" },
    { id: "OT1003", due: 20, qty: 700, cluster: 3, format: "A" },
    { id: "OT1004", due: 28, qty: 1200, cluster: 2, format: "C" },
    { id: "OT1005", due: 30, qty: 600, cluster: 4, format: "B" },
    { id: "OT1006", due: 40, qty: 1500, cluster: 1, format: "A" },
    { id: "OT1007", due: 45, qty: 900, cluster: 2, format: "C" },
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
  start_datetime: "2024-01-25T08:00:00",
  work_hours_per_day: 24.0,
  work_start_hour: 0,
  work_days: [0, 1, 2, 3, 4, 5, 6],
};

// Usar el modelo optimizado por defecto
export const datosTesteo = datosTesteoOptimizado;

// =====================================================
// FUNCIÓN PARA OBTENER LOS LOGS
// =====================================================
export async function fetchScheduleLogs(useOptimized = true) {
  try {
    // URL del endpoint - IMPORTANTE: usar el puerto 8000 del backend
    const API_URL = 'http://localhost:8000/api/schedule';
    
    // Preparar los datos a enviar
    const requestBody = useOptimized ? datosTesteoOptimizado : datosTesteoAntiguo;

    console.log('🔬 MODO:', useOptimized ? 'Modelo Optimizado (múltiples productos)' : 'Formato Antiguo (compatibilidad)');
    console.log('📡 Enviando request a:', API_URL);
    console.log('📦 Datos:', requestBody);

    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    // Verificar si la respuesta es exitosa
    if (!response.ok) {
      // Si hay error, obtener los detalles
      const errorData = await response.json();
      console.error('❌ Schedule API Error:', errorData);
      
      // El error 422 generalmente muestra qué campos faltan o están mal
      if (response.status === 422) {
        throw new Error(
          `Error de validación: ${JSON.stringify(errorData.detail)}\n` +
          `Asegúrate de enviar 'orders' y 'machines' como mínimo.`
        );
      }
      
      // El error 500 puede indicar que el problema no es factible
      if (response.status === 500) {
        const errorMsg = errorData.detail || errorData.message || JSON.stringify(errorData);
        if (errorMsg.includes('NO FACTIBLE') || errorMsg.includes('no pueden completarse')) {
          throw new Error(
            `⚠️ PROBLEMA NO FACTIBLE: ${errorMsg}\n` +
            `No es posible completar todas las OTs antes de sus fechas límite.`
          );
        }
      }
      
      throw new Error(`Error: ${JSON.stringify(errorData)} (Status: ${response.status})`);
    }

    // Parsear la respuesta
    const resultado = await response.json();
    
    console.log('✅ Respuesta recibida exitosamente');
    console.log('📊 Resumen:', resultado.summary);
    
    // Los logs están en resultado.logs (array de strings)
    return {
      logs: resultado.logs || [],
      schedule: resultado.schedule || [],
      schedule_by_machine: resultado.schedule_by_machine || {},
      summary: resultado.summary || {},
    };
    
  } catch (error) {
    console.error('❌ Error fetching schedule logs:', error);
    throw error;
  }
}

// =====================================================
// EJEMPLO DE USO EN UN COMPONENTE REACT
// =====================================================
// 
// Ver EJEMPLO_FRONTEND.md para ejemplos completos de componentes React
// con JSX. Aquí solo mostramos la lógica de JavaScript.
//
// Ejemplo básico:
// import { fetchScheduleLogs, datosTesteoOptimizado } from './ejemplo_useProductionData';
//
// function ProductionConsole() {
//   const [logs, setLogs] = React.useState([]);
//   const [loading, setLoading] = React.useState(false);
//   const [error, setError] = React.useState(null);
//
//   const handleConsoleClick = async () => {
//     setLoading(true);
//     setError(null);
//     try {
//       const resultado = await fetchScheduleLogs(true);
//       setLogs(resultado.logs);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setLoading(false);
//     }
//   };
//
//   return (
//     <div>
//       <button onClick={handleConsoleClick} disabled={loading}>
//         {loading ? 'Cargando...' : 'Ver Logs de Producción'}
//       </button>
//       {error && <div style={{ color: 'red' }}>Error: {error}</div>}
//       <div style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
//         {logs.map((line, index) => <div key={index}>{line}</div>)}
//       </div>
//     </div>
//   );
// }

// =====================================================
// EJEMPLO MÍNIMO (solo campos requeridos)
// =====================================================
export async function fetchScheduleLogsMinimo() {
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

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(`Error: ${JSON.stringify(errorData)}`);
  }

  const resultado = await response.json();
  return resultado.logs;
}

// =====================================================
// FUNCIÓN PARA PROCESAR Y MOSTRAR LOGS EN CONSOLA
// =====================================================
export function mostrarLogsEnConsola(logs) {
  // logs es un array de strings
  logs.forEach(line => {
    console.log(line);
  });
}

// =====================================================
// FUNCIÓN PARA OBTENER INFORMACIÓN DE UNA TAREA
// =====================================================
export function obtenerInfoTarea(task) {
  if (task.type === 'PRODUCTION') {
    return {
      tipo: 'Producción',
      producto: task.product || task.format,
      cantidad: task.quantity,
      otIds: task.ot_ids || [],
      maquina: task.machine,
      inicio: task.start_datetime_str || `${task.start}h`,
      fin: task.end_datetime_str || `${task.end}h`,
      duracion: task.duration,
      aTiempo: task.on_time
    };
  } else if (task.type === 'SETUP') {
    return {
      tipo: 'Setup',
      cambioA: task.format,
      maquina: task.machine,
      inicio: task.start_datetime_str || `${task.start}h`,
      fin: task.end_datetime_str || `${task.end}h`,
      duracion: task.duration
    };
  } else {
    return {
      tipo: 'OT',
      id: task.id,
      formato: task.format,
      maquina: task.machine,
      inicio: task.start_datetime_str || `${task.start}h`,
      fin: task.end_datetime_str || `${task.end}h`,
      duracion: task.duration,
      aTiempo: task.on_time
    };
  }
}
