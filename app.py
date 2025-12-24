from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple, Any
from copy import deepcopy

app = FastAPI(
    title="Barron Production Scheduler API",
    description="API para programación heurística de producción",
    version="1.0.0"
)

# =====================================================
# MODELOS PYDANTIC PARA VALIDACIÓN
# =====================================================

class Order(BaseModel):
    id: str = Field(..., description="Identificador único de la OT")
    due: float = Field(..., gt=0, description="Fecha compromiso en horas desde ahora")
    qty: int = Field(..., gt=0, description="Cantidad solicitada por el cliente")
    cluster: int = Field(..., gt=0, description="Prioridad comercial (mayor = más importante)")
    format: str = Field(..., description="Formato / cuchillo / dimensión")

class Machine(BaseModel):
    capacity: float = Field(..., gt=0, description="Unidades producidas por hora")
    available_at: float = Field(default=0, ge=0, description="Reloj interno de la máquina")
    last_format: Optional[str] = Field(default=None, description="Último formato producido")

class ScheduleRequest(BaseModel):
    orders: List[Order] = Field(..., description="Lista de órdenes de trabajo")
    machines: Dict[str, Machine] = Field(..., description="Diccionario de máquinas disponibles")
    setup_times: Optional[Dict[str, float]] = Field(
        default=None,
        description="Diccionario con tiempos de setup. Formato: {'A-B': 1.5, 'B-A': 1.5, ...}"
    )
    horizonte_aprovechamiento: float = Field(default=12, gt=0, description="Ventana futura en horas para producir adelantado")
    costo_inventario_unitario: float = Field(default=0.002, ge=0, description="Costo ficticio por unidad y hora de mantener stock")
    default_setup_time: float = Field(default=1.5, gt=0, description="Tiempo de setup por defecto cuando no se especifica")

class ScheduleItem(BaseModel):
    type: str = Field(..., description="Tipo: 'SETUP' o 'OT'")
    machine: Optional[str] = Field(default=None, description="Máquina asignada")
    start: float = Field(..., description="Hora de inicio en horas")
    end: float = Field(..., description="Hora de fin en horas")
    duration: float = Field(..., description="Duración en horas (calculada automáticamente)")
    id: Optional[str] = Field(default=None, description="ID de la OT (solo para tipo OT)")
    due: Optional[float] = Field(default=None, description="Fecha compromiso (solo para tipo OT)")
    qty_cliente: Optional[int] = Field(default=None, description="Cantidad para cliente (solo para tipo OT)")
    qty_extra: Optional[int] = Field(default=None, description="Cantidad extra producida (solo para tipo OT)")
    format: Optional[str] = Field(default=None, description="Formato (solo para tipo OT)")
    color: Optional[str] = Field(default=None, description="Color sugerido para visualización (solo para tipo OT)")
    on_time: Optional[bool] = Field(default=None, description="Si la OT está a tiempo (solo para tipo OT)")

class MachineSchedule(BaseModel):
    machine: str = Field(..., description="Nombre de la máquina")
    tasks: List[ScheduleItem] = Field(..., description="Lista de tareas ordenadas por tiempo")

class ScheduleResponse(BaseModel):
    schedule: List[ScheduleItem] = Field(..., description="Secuencia temporal de todas las tareas")
    schedule_by_machine: Dict[str, List[ScheduleItem]] = Field(..., description="Tareas agrupadas por máquina (ideal para Gantt)")
    summary: Dict[str, Any] = Field(..., description="Resumen estadístico del programa")

# =====================================================
# FUNCIONES DE LÓGICA DE NEGOCIO
# =====================================================

def calcular_prioridad(ot: Order) -> float:
    """Calcula la prioridad de una OT: due / cluster"""
    return ot.due / ot.cluster

def futuras_mismo_formato(ot_actual: Order, todas: List[Order], horizonte: float) -> List[Order]:
    """Encuentra OT futuras del mismo formato dentro del horizonte"""
    return [
        o for o in todas
        if o.format == ot_actual.format
        and o.due > ot_actual.due
        and o.due <= ot_actual.due + horizonte
    ]

def conviene_aprovechar(ot: Order, futuras: List[Order], horizonte: float, costo_inv: float) -> int:
    """Decide si conviene producir extra para aprovechar el rollo"""
    if not futuras:
        return 0

    qty_futura = sum(o.qty for o in futuras)
    ahorro_setup = 1.5  # horas promedio evitadas
    costo_inventario = qty_futura * costo_inv * horizonte

    if ahorro_setup > costo_inventario:
        return int(qty_futura * 0.5)  # producimos 50% adelantado
    return 0

def calcular_setup_time(
    prev_fmt: Optional[str],
    new_fmt: str,
    setup_times_dict: Dict[str, float],
    default_setup: float
) -> float:
    """Calcula el tiempo de setup necesario"""
    if prev_fmt is None or prev_fmt == new_fmt:
        return 0
    
    key = f"{prev_fmt}-{new_fmt}"
    return setup_times_dict.get(key, default_setup)

def convertir_setup_times(setup_times: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Convierte setup_times de formato tupla a formato string para facilitar el acceso"""
    if setup_times is None:
        return {}
    return setup_times

def programar_produccion(
    orders: List[Order],
    machines_dict: Dict[str, Machine],
    setup_times: Optional[Dict[str, float]],
    horizonte: float,
    costo_inv: float,
    default_setup: float
) -> Tuple[List[ScheduleItem], Dict[str, List[ScheduleItem]], Dict]:
    """Función principal que ejecuta el algoritmo de programación"""
    
    # Convertir setup_times a formato interno si es necesario
    setup_times_dict = convertir_setup_times(setup_times)
    
    # Crear copias profundas para no modificar los originales
    machines = deepcopy(machines_dict)
    orders_sorted = sorted(orders, key=calcular_prioridad)
    
    schedule = []
    
    for ot in orders_sorted:
        futuras = futuras_mismo_formato(ot, orders_sorted, horizonte)
        extra_qty = conviene_aprovechar(ot, futuras, horizonte, costo_inv)
        total_qty = ot.qty + extra_qty

        best_machine = None
        best_end = None
        best_setup = 0

        for m_name, machine_data in machines.items():
            st = calcular_setup_time(
                machine_data.last_format,
                ot.format,
                setup_times_dict,
                default_setup
            )
            duration = total_qty / machine_data.capacity
            end_time = machine_data.available_at + st + duration

            if best_end is None or end_time < best_end:
                best_end = end_time
                best_machine = m_name
                best_setup = st

        if best_machine is None:
            continue  # No debería pasar, pero por seguridad

        start_time = machines[best_machine].available_at

        if best_setup > 0:
            setup_end = start_time + best_setup
            schedule.append(ScheduleItem(
                type="SETUP",
                machine=best_machine,
                start=start_time,
                end=setup_end,
                duration=best_setup,
                color="#808080"  # Gris para setups
            ))
            start_time += best_setup

        on_time = best_end <= ot.due
        # Color sugerido: azul claro para producción, gris para setups
        schedule.append(ScheduleItem(
            type="OT",
            id=ot.id,
            machine=best_machine,
            start=start_time,
            end=best_end,
            duration=best_end - start_time,
            due=ot.due,
            qty_cliente=ot.qty,
            qty_extra=extra_qty,
            format=ot.format,
            color="#4A90E2",  # Azul claro para producción
            on_time=on_time
        ))

        machines[best_machine].available_at = best_end
        machines[best_machine].last_format = ot.format

    # Calcular resumen estadístico
    total_ots = len([s for s in schedule if s.type == "OT"])
    total_setups = len([s for s in schedule if s.type == "SETUP"])
    total_horas = max([s.end for s in schedule], default=0)
    qty_total_cliente = sum([s.qty_cliente for s in schedule if s.qty_cliente is not None])
    qty_total_extra = sum([s.qty_extra for s in schedule if s.qty_extra is not None])
    
    # Calcular atrasos
    atrasos = []
    for s in schedule:
        if s.type == "OT" and s.end is not None and s.due is not None:
            if s.end > s.due:
                # Buscar el cluster de la OT
                ot_original = next((o for o in orders if o.id == s.id), None)
                if ot_original:
                    atrasos.append({
                        "ot_id": s.id,
                        "atraso_horas": s.end - s.due,
                        "cluster": ot_original.cluster
                    })
    
    summary = {
        "total_ots": total_ots,
        "total_setups": total_setups,
        "total_horas": round(total_horas, 2),
        "qty_total_cliente": qty_total_cliente,
        "qty_total_extra": qty_total_extra,
        "atrasos": atrasos,
        "horizonte_usado": horizonte
    }
    
    # Agrupar por máquina para facilitar visualización tipo Gantt
    schedule_by_machine: Dict[str, List[ScheduleItem]] = {}
    for task in schedule:
        machine = task.machine
        if machine:
            if machine not in schedule_by_machine:
                schedule_by_machine[machine] = []
            schedule_by_machine[machine].append(task)
    
    # Ordenar tareas dentro de cada máquina por hora de inicio
    for machine in schedule_by_machine:
        schedule_by_machine[machine].sort(key=lambda x: x.start)
    
    return schedule, schedule_by_machine, summary

# =====================================================
# ENDPOINTS API
# =====================================================

@app.get("/")
def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "Barron Production Scheduler API",
        "version": "1.0.0",
        "endpoints": {
            "/schedule": "POST - Programa la producción",
            "/docs": "Documentación interactiva (Swagger UI)",
            "/redoc": "Documentación alternativa (ReDoc)"
        }
    }

@app.post("/schedule", response_model=ScheduleResponse)
def crear_programa(request: ScheduleRequest):
    """
    Endpoint principal que recibe las órdenes de trabajo y máquinas,
    y devuelve el programa de producción optimizado.
    """
    try:
        schedule, schedule_by_machine, summary = programar_produccion(
            orders=request.orders,
            machines_dict=request.machines,
            setup_times=request.setup_times,
            horizonte=request.horizonte_aprovechamiento,
            costo_inv=request.costo_inventario_unitario,
            default_setup=request.default_setup_time
        )
        
        return ScheduleResponse(
            schedule=schedule,
            schedule_by_machine=schedule_by_machine,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el programa: {str(e)}")

@app.get("/health")
def health_check():
    """Endpoint de salud para verificar que la API está funcionando"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

