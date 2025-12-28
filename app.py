from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple, Any
from copy import deepcopy
from datetime import datetime, timedelta

app = FastAPI(
    title="Barron Production Scheduler API",
    description="API para programación heurística de producción",
    version="1.0.0"
)

# Router con prefijo /api
api_router = APIRouter(prefix="/api")

# =====================================================
# MODELOS PYDANTIC PARA VALIDACIÓN
# =====================================================

class Order(BaseModel):
    id: str = Field(..., description="Identificador único de la OT")
    due: float = Field(..., gt=0, description="Fecha compromiso en horas desde ahora")
    cluster: int = Field(..., gt=0, description="Prioridad comercial (mayor = más importante)")
    # Soporte para múltiples productos (nuevo formato)
    products: Optional[Dict[str, int]] = Field(
        default=None,
        description="Diccionario de productos y cantidades. Ej: {'A': 100, 'B': 200}. Si no se proporciona, se usa 'format' y 'qty' para compatibilidad"
    )
    # Campos para compatibilidad con formato anterior
    qty: Optional[int] = Field(default=None, ge=0, description="Cantidad solicitada (solo si products no se proporciona)")
    format: Optional[str] = Field(default=None, description="Formato/producto único (solo si products no se proporciona)")
    
    def get_products(self) -> Dict[str, int]:
        """Obtiene el diccionario de productos, convirtiendo formato antiguo si es necesario"""
        if self.products is not None:
            return self.products
        elif self.format is not None and self.qty is not None:
            # Compatibilidad con formato anterior
            return {self.format: self.qty}
        else:
            raise ValueError(f"Order {self.id} debe tener 'products' o ('format' y 'qty')")

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
    start_datetime: Optional[str] = Field(
        default=None,
        description="Fecha y hora de inicio de producción en formato ISO (YYYY-MM-DDTHH:MM:SS). Si no se especifica, se usa la fecha/hora actual"
    )
    work_hours_per_day: float = Field(default=24.0, gt=0, le=24, description="Horas de trabajo por día (24.0 para producción 24/7)")
    work_start_hour: int = Field(default=0, ge=0, le=23, description="Hora de inicio del día laboral (no se usa en modo 24/7)")
    work_days: List[int] = Field(default=[0, 1, 2, 3, 4, 5, 6], description="Días de la semana que se trabaja (todos los días para 24/7)")

class ScheduleItem(BaseModel):
    type: str = Field(..., description="Tipo: 'SETUP' o 'PRODUCTION'")
    machine: Optional[str] = Field(default=None, description="Máquina asignada")
    start: float = Field(..., description="Hora de inicio en horas")
    end: float = Field(..., description="Hora de fin en horas")
    duration: float = Field(..., description="Duración en horas (calculada automáticamente)")
    # Campos para compatibilidad con formato anterior
    id: Optional[str] = Field(default=None, description="ID de la OT (compatibilidad)")
    due: Optional[float] = Field(default=None, description="Fecha compromiso (compatibilidad)")
    qty_cliente: Optional[int] = Field(default=None, description="Cantidad para cliente (compatibilidad)")
    qty_extra: Optional[int] = Field(default=None, description="Cantidad extra producida (compatibilidad)")
    format: Optional[str] = Field(default=None, description="Producto/formato producido")
    # Nuevos campos para producción optimizada
    product: Optional[str] = Field(default=None, description="Producto producido en esta tarea")
    quantity: Optional[int] = Field(default=None, description="Cantidad producida de este producto")
    ot_ids: Optional[List[str]] = Field(default=None, description="IDs de OTs que se completan con esta producción")
    color: Optional[str] = Field(default=None, description="Color sugerido para visualización")
    on_time: Optional[bool] = Field(default=None, description="Si todas las OTs relacionadas están a tiempo")
    start_datetime_str: Optional[str] = Field(default=None, description="Fecha y hora de inicio formateada (ej: '8:00 AM lunes 25')")
    end_datetime_str: Optional[str] = Field(default=None, description="Fecha y hora de fin formateada (ej: '3:00 PM lunes 25')")

class MachineSchedule(BaseModel):
    machine: str = Field(..., description="Nombre de la máquina")
    tasks: List[ScheduleItem] = Field(..., description="Lista de tareas ordenadas por tiempo")

class ScheduleResponse(BaseModel):
    schedule: List[ScheduleItem] = Field(..., description="Secuencia temporal de todas las tareas")
    schedule_by_machine: Dict[str, List[ScheduleItem]] = Field(..., description="Tareas agrupadas por máquina (ideal para Gantt)")
    summary: Dict[str, Any] = Field(..., description="Resumen estadístico del programa")
    logs: List[str] = Field(..., description="Logs formateados para mostrar en consola del frontend")

# =====================================================
# FUNCIONES DE LÓGICA DE NEGOCIO
# =====================================================

def calcular_prioridad(ot: Order) -> float:
    """Calcula la prioridad de una OT: due / cluster"""
    return ot.due / ot.cluster

def futuras_mismo_formato(ot_actual: Order, todas: List[Order], horizonte: float) -> List[Order]:
    """Encuentra OT futuras del mismo formato dentro del horizonte (compatibilidad con formato antiguo)"""
    try:
        # Intentar obtener productos del formato nuevo
        products_actual = ot_actual.get_products()
        if len(products_actual) == 1:
            # Si tiene un solo producto, usar formato antiguo
            format_actual = list(products_actual.keys())[0]
            return [
                o for o in todas
                if o.id != ot_actual.id
                and o.due > ot_actual.due
                and o.due <= ot_actual.due + horizonte
                and format_actual in o.get_products()
            ]
    except:
        # Formato antiguo: usar format directamente
        if ot_actual.format:
            return [
                o for o in todas
                if o.format == ot_actual.format
                and o.due > ot_actual.due
                and o.due <= ot_actual.due + horizonte
            ]
    return []

def conviene_aprovechar(ot: Order, futuras: List[Order], horizonte: float, costo_inv: float) -> int:
    """Decide si conviene producir extra para aprovechar el rollo (compatibilidad con formato antiguo)"""
    if not futuras:
        return 0

    # Calcular cantidad futura (compatibilidad con ambos formatos)
    qty_futura = 0
    try:
        products_actual = ot.get_products()
        if len(products_actual) == 1:
            format_actual = list(products_actual.keys())[0]
            for o in futuras:
                products_o = o.get_products()
                if format_actual in products_o:
                    qty_futura += products_o[format_actual]
    except:
        # Formato antiguo
        qty_futura = sum(o.qty for o in futuras if o.qty)
    
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

def horas_a_fecha_hora(
    horas_acumuladas: float,
    fecha_inicio: datetime,
    horas_por_dia: float = 24.0,
    hora_inicio_dia: int = 0,
    dias_trabajo: List[int] = None
) -> datetime:
    """
    Convierte horas acumuladas desde el inicio de producción a fecha/hora real.
    Producción 24/7: simplemente suma las horas a la fecha de inicio.
    
    Args:
        horas_acumuladas: Horas desde el inicio de producción
        fecha_inicio: Fecha y hora de inicio de producción
        horas_por_dia: No se usa en modo 24/7 (mantenido por compatibilidad)
        hora_inicio_dia: No se usa en modo 24/7 (mantenido por compatibilidad)
        dias_trabajo: No se usa en modo 24/7 (mantenido por compatibilidad)
    
    Returns:
        datetime con la fecha y hora real correspondiente
    """
    # Producción 24/7: simplemente sumar las horas directamente
    return fecha_inicio + timedelta(hours=horas_acumuladas)

def formatear_fecha_hora(dt: datetime) -> str:
    """
    Formatea una fecha/hora a un string legible en español.
    Ejemplo: "8:00 AM lunes 25"
    """
    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    
    dia_semana = dias_semana[dt.weekday()]
    dia = dt.day
    hora = dt.hour
    minuto = dt.minute
    
    # Formato de hora (AM/PM)
    if hora == 0:
        hora_str = "12"
        periodo = "AM"
    elif hora < 12:
        hora_str = str(hora)
        periodo = "AM"
    elif hora == 12:
        hora_str = "12"
        periodo = "PM"
    else:
        hora_str = str(hora - 12)
        periodo = "PM"
    
    minuto_str = f":{minuto:02d}" if minuto > 0 else ""
    
    return f"{hora_str}{minuto_str} {periodo} {dia_semana} {dia}"

def generar_logs(
    schedule: List[ScheduleItem],
    schedule_by_machine: Dict[str, List[ScheduleItem]],
    summary: Dict[str, Any]
) -> List[str]:
    """
    Genera logs formateados en el mismo formato que se muestra en test_api.py.
    Retorna una lista de strings, cada uno es una línea del log.
    """
    logs = []
    
    # Programa de producción generado
    logs.append("=" * 60)
    logs.append("PROGRAMA DE PRODUCCIÓN GENERADO")
    logs.append("=" * 60)
    logs.append("")
    
    for task in schedule:
        if task.type == "SETUP":
            logs.append(f"🔧 [{task.machine}] SETUP")
            logs.append(f"   ⏱️  {task.start:.2f}h → {task.end:.2f}h")
            logs.append(f"   ⏳ Duración: {task.duration:.2f}h")
            if task.format:
                logs.append(f"   🏷️  Cambio a: {task.format}")
            if task.color:
                logs.append(f"   🎨 Color: {task.color}")
            logs.append("")
        elif task.type == "PRODUCTION":
            # Formato nuevo: producción optimizada
            product = task.product or task.format or "Producto"
            quantity = task.quantity or task.qty_cliente or 0
            ot_ids = task.ot_ids or ([task.id] if task.id else [])
            
            logs.append(f"📦 [{task.machine}] Producción: {product}")
            logs.append(f"   ⏱️  {task.start:.2f}h → {task.end:.2f}h")
            logs.append(f"   📊 Cantidad: {quantity} unidades")
            if ot_ids:
                logs.append(f"   📋 OTs beneficiadas: {', '.join(ot_ids)}")
            on_time = task.on_time if task.on_time is not None else True
            logs.append(f"   {'✅ A TIEMPO' if on_time else '⚠️ ATRASADO'}")
            if task.color:
                logs.append(f"   🎨 Color: {task.color}")
            logs.append("")
        else:
            # Formato antiguo: compatibilidad
            logs.append(f"📋 [{task.machine}] {task.id or 'OT'}")
            logs.append(f"   ⏱️  {task.start:.2f}h → {task.end:.2f}h")
            on_time = task.on_time if task.on_time is not None else (task.end <= task.due if task.due else True)
            if task.due:
                logs.append(f"   📅 Due: {task.due:.2f}h {'✅ A TIEMPO' if on_time else '⚠️ ATRASADO'}")
            if task.qty_cliente:
                logs.append(f"   📦 Cliente: {task.qty_cliente} unidades")
            if task.qty_extra:
                logs.append(f"   ➕ Extra: {task.qty_extra} unidades")
            if task.format:
                logs.append(f"   🏷️  Formato: {task.format}")
            if task.color:
                logs.append(f"   🎨 Color: {task.color}")
            logs.append("")
    
    # Resumen estadístico
    logs.append("=" * 60)
    logs.append("RESUMEN ESTADÍSTICO")
    logs.append("=" * 60)
    logs.append(f"📊 Total OTs procesadas: {summary['total_ots']}")
    logs.append(f"🔧 Total Setups realizados: {summary['total_setups']}")
    logs.append(f"⏰ Total de horas programadas: {summary['total_horas']:.2f}h")
    logs.append(f"📦 Cantidad total para cliente: {summary['qty_total_cliente']} unidades")
    logs.append(f"➕ Cantidad total extra: {summary['qty_total_extra']} unidades")
    
    if summary.get('atrasos') and len(summary['atrasos']) > 0:
        logs.append("")
        logs.append(f"⚠️ ATRASOS DETECTADOS: {len(summary['atrasos'])} OTs")
        logs.append("")
        for atraso in summary['atrasos']:
            due_time = atraso.get('due', 0)
            completion_time = atraso.get('completion', due_time + atraso['atraso_horas'])
            logs.append(f"   ⚠️ {atraso['ot_id']}:")
            logs.append(f"      📅 Fecha límite: {due_time:.2f}h")
            logs.append(f"      ⏰ Completación: {completion_time:.2f}h")
            logs.append(f"      ⏳ Atraso: {atraso['atraso_horas']:.2f}h (cluster {atraso['cluster']})")
            logs.append("")
        logs.append("ℹ️  NOTA: Estas OTs se entregarán fuera del plazo, pero se programaron")
        logs.append("   para minimizar el atraso y completar la producción lo antes posible.")
    else:
        logs.append("")
        logs.append("✅ Todas las OTs están a tiempo")
    
    # Vista por máquina
    if schedule_by_machine:
        logs.append("")
        logs.append("=" * 60)
        logs.append("VISTA POR MÁQUINA (para visualización Gantt)")
        logs.append("=" * 60)
        for machine, tasks in schedule_by_machine.items():
            logs.append(f"")
            logs.append(f"🏭 {machine}: {len(tasks)} tareas")
            for task in tasks:
                if task.type == "SETUP":
                    task_type = "🔧 SETUP"
                    product_info = f" → {task.format}" if task.format else ""
                elif task.type == "PRODUCTION":
                    product = task.product or task.format or "Producto"
                    task_type = f"📦 {product}"
                else:
                    task_type = f"📋 {task.id if task.id else 'OT'}"
                
                # Mostrar fecha/hora si está disponible, sino mostrar horas
                if task.start_datetime_str and task.end_datetime_str:
                    logs.append(f"   {task_type} - {task.start_datetime_str} → {task.end_datetime_str} ({task.duration:.2f}h)")
                else:
                    logs.append(f"   {task_type} - {task.start:.2f}h → {task.end:.2f}h ({task.duration:.2f}h)")
    
    logs.append("")
    logs.append("=" * 60)
    logs.append("✅ PRUEBA COMPLETADA EXITOSAMENTE")
    logs.append("=" * 60)
    
    return logs

# =====================================================
# NUEVO MODELO DE OPTIMIZACIÓN CON MÚLTIPLES PRODUCTOS
# =====================================================

class ProductTask:
    """Representa una tarea de producción de un producto específico"""
    def __init__(self, product: str, quantity: int, ot_id: str, ot_due: float, ot_cluster: int):
        self.product = product
        self.quantity = quantity
        self.ot_id = ot_id
        self.ot_due = ot_due
        self.ot_cluster = ot_cluster
        self.assigned_machine: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

def descomponer_ots_en_tareas(orders: List[Order]) -> Tuple[List[ProductTask], Dict[str, Dict[str, int]]]:
    """
    Descompone OTs en tareas de productos individuales.
    Retorna: (lista de tareas, diccionario de productos por OT)
    """
    tasks = []
    ot_products = {}  # {ot_id: {product: quantity}}
    
    for ot in orders:
        products = ot.get_products()
        ot_products[ot.id] = products
        
        for product, quantity in products.items():
            tasks.append(ProductTask(
                product=product,
                quantity=quantity,
                ot_id=ot.id,
                ot_due=ot.due,
                ot_cluster=ot.cluster
            ))
    
    return tasks, ot_products

def calcular_fecha_limite_producto(product: str, tasks: List[ProductTask]) -> float:
    """
    Calcula la fecha límite más temprana para un producto.
    Es la fecha 'due' más temprana de todas las OTs que requieren ese producto.
    """
    product_tasks = [t for t in tasks if t.product == product]
    if not product_tasks:
        return float('inf')
    return min(t.ot_due for t in product_tasks)

def verificar_factibilidad(
    orders: List[Order],
    machines_dict: Dict[str, Machine],
    setup_times_dict: Dict[str, float],
    default_setup: float
) -> Tuple[bool, Optional[str]]:
    """
    Verifica si es factible completar todas las OTs antes de sus fechas límite.
    Retorna: (es_factible, mensaje_error)
    """
    tasks, _ = descomponer_ots_en_tareas(orders)
    
    # Agrupar tareas por producto
    products_needed = {}
    for task in tasks:
        if task.product not in products_needed:
            products_needed[task.product] = 0
        products_needed[task.product] += task.quantity
    
    # Calcular tiempo mínimo necesario para cada producto
    total_capacity = sum(m.capacity for m in machines_dict.values())
    
    for product, total_qty in products_needed.items():
        # Tiempo mínimo de producción (sin setups)
        min_production_time = total_qty / total_capacity
        
        # Tiempo mínimo con setups (asumiendo un setup por máquina)
        num_machines = len(machines_dict)
        min_setup_time = num_machines * default_setup
        min_total_time = min_production_time + min_setup_time
        
        # Verificar si alguna OT que requiere este producto tiene fecha límite muy cercana
        product_tasks = [t for t in tasks if t.product == product]
        earliest_due = min(t.ot_due for t in product_tasks)
        
        if min_total_time > earliest_due:
            return False, f"Producto {product}: tiempo mínimo requerido ({min_total_time:.2f}h) excede fecha límite más temprana ({earliest_due:.2f}h)"
    
    return True, None

def evaluar_distribucion_paralela(
    product: str,
    total_quantity: int,
    machines: Dict[str, Machine],
    setup_times_dict: Dict[str, float],
    default_setup: float
) -> Tuple[List[Tuple[str, float, float, float, float]], float]:
    """
    Evalúa diferentes formas de distribuir un producto entre máquinas.
    Retorna: (asignaciones, makespan)
    donde asignaciones es [(machine_name, quantity, start_time, end_time, setup_time), ...]
    """
    if len(machines) <= 1:
        # Solo una máquina disponible, usar esa
        m_name = list(machines.keys())[0]
        m_data = machines[m_name]
        setup_time = calcular_setup_time(
            m_data.last_format,
            product,
            setup_times_dict,
            default_setup
        )
        production_time = total_quantity / m_data.capacity
        end_time = m_data.available_at + setup_time + production_time
        return [(m_name, total_quantity, m_data.available_at, end_time, setup_time)], end_time
    
    # Calcular tiempos de inicio considerando setups para todas las máquinas
    machine_info = []
    for m_name, m_data in machines.items():
        setup_time = calcular_setup_time(
            m_data.last_format,
            product,
            setup_times_dict,
            default_setup
        )
        start_time = m_data.available_at + setup_time
        machine_info.append((m_name, start_time, setup_time, m_data))
    
    # Ordenar por tiempo de inicio (más disponibles primero)
    machine_info.sort(key=lambda x: (x[1], -x[3].capacity))  # Por tiempo, luego por capacidad
    
    # Opción 1: Todo en la mejor máquina individual
    best_single = machine_info[0]
    best_single_machine, best_single_start, best_single_setup, best_single_data = best_single
    best_single_production_time = total_quantity / best_single_data.capacity
    best_single_end = best_single_start + best_single_production_time
    
    single_option = [(best_single_machine, total_quantity, 
                     machines[best_single_machine].available_at,
                     best_single_end, best_single_setup)]
    
    # Opción 2: Distribuir entre todas las máquinas disponibles en paralelo
    # Calcular capacidad total y tiempos
    total_capacity = sum(m[3].capacity for m in machine_info)
    earliest_start = machine_info[0][1]
    latest_start = machine_info[-1][1]
    time_spread = latest_start - earliest_start
    
    # Si el spread es muy grande (más del 30% del tiempo de producción), 
    # puede que no valga la pena distribuir
    single_production_time = total_quantity / best_single_data.capacity
    if time_spread > single_production_time * 0.3 and len(machine_info) == 2:
        # Solo considerar si hay más de 2 máquinas o el spread es razonable
        pass
    
    # Distribuir cantidad proporcionalmente a capacidad, ajustando para que terminen juntas
    parallel_assignments = []
    remaining_qty = total_quantity
    
    # Calcular cuánto puede producir cada máquina hasta que todas estén listas
    # Objetivo: que todas terminen aproximadamente al mismo tiempo
    target_end_time = earliest_start + (total_quantity / total_capacity)
    
    for m_name, start_time, setup_time, m_data in machine_info:
        if remaining_qty <= 0:
            break
        
        # Tiempo disponible desde que esta máquina está lista hasta el target
        time_available = max(0, target_end_time - start_time)
        
        if time_available <= 0:
            # Esta máquina no puede ayudar porque está muy ocupada
            continue
        
        # Calcular cantidad proporcional a capacidad
        capacity_ratio = m_data.capacity / total_capacity
        qty_this = int(total_quantity * capacity_ratio)
        
        # Asegurar que no exceda el tiempo disponible ni la cantidad restante
        max_qty_by_time = int(m_data.capacity * time_available)
        qty_this = min(qty_this, max_qty_by_time, remaining_qty)
        
        # Asegurar al menos una cantidad mínima razonable
        if qty_this < total_quantity * 0.1 and len(parallel_assignments) > 0:
            # Si es muy poca cantidad, mejor no asignar a esta máquina
            continue
        
        if qty_this > 0:
            production_time = qty_this / m_data.capacity
            end_time = start_time + production_time
            parallel_assignments.append((m_name, qty_this, start_time, end_time, setup_time))
            remaining_qty -= qty_this
    
    # Si quedó cantidad sin asignar, distribuirla proporcionalmente entre las máquinas asignadas
    if remaining_qty > 0 and parallel_assignments:
        total_assigned_capacity = sum(machines[m[0]].capacity for m in parallel_assignments)
        for idx, (m_name, qty, start, end, setup) in enumerate(parallel_assignments):
            if remaining_qty <= 0:
                break
            capacity_ratio = machines[m_name].capacity / total_assigned_capacity
            additional_qty = min(remaining_qty, max(1, int(remaining_qty * capacity_ratio)))
            if additional_qty > 0:
                additional_time = additional_qty / machines[m_name].capacity
                new_end = end + additional_time
                parallel_assignments[idx] = (m_name, qty + additional_qty, start, new_end, setup)
                remaining_qty -= additional_qty
    
    # Si aún queda cantidad, dársela a la máquina más rápida disponible
    if remaining_qty > 0:
        if parallel_assignments:
            # Agregar a la máquina más rápida de las ya asignadas
            fastest_idx = max(range(len(parallel_assignments)), 
                             key=lambda i: machines[parallel_assignments[i][0]].capacity)
            m_name, qty, start, end, setup = parallel_assignments[fastest_idx]
            additional_time = remaining_qty / machines[m_name].capacity
            new_end = end + additional_time
            parallel_assignments[fastest_idx] = (m_name, qty + remaining_qty, start, new_end, setup)
        else:
            # Si no hay asignaciones paralelas, usar la mejor máquina individual
            return single_option, best_single_end
    
    # Calcular makespan paralelo (máximo tiempo de fin)
    if parallel_assignments:
        parallel_end = max(end for _, _, _, end, _ in parallel_assignments)
        
        # Usar paralelo si:
        # 1. Hay al menos 2 máquinas asignadas
        # 2. El makespan es mejor O similar (dentro del 10%)
        # 3. O si la cantidad es grande (más de 1000 unidades), siempre distribuir
        if len(parallel_assignments) > 1:
            if parallel_end <= best_single_end * 1.1 or total_quantity > 1000:
                return parallel_assignments, parallel_end
    
    # Si no se cumplen las condiciones, usar una sola máquina
    return single_option, best_single_end

def programar_produccion_optimizada(
    orders: List[Order],
    machines_dict: Dict[str, Machine],
    setup_times: Optional[Dict[str, float]],
    default_setup: float
) -> Tuple[List[ScheduleItem], Dict[str, List[ScheduleItem]], Dict]:
    """
    Algoritmo de programación optimizada que:
    1. Descompone OTs en tareas de productos
    2. Agrupa productos del mismo tipo para minimizar setups
    3. Distribuye productos entre máquinas en paralelo cuando es beneficioso
    4. Minimiza el makespan total
    5. Optimiza para minimizar OTs atrasadas (no rechaza si no es factible)
    """
    setup_times_dict = convertir_setup_times(setup_times)
    
    # Descomponer OTs en tareas de productos
    tasks, ot_products = descomponer_ots_en_tareas(orders)
    
    # Crear copias de máquinas
    machines = deepcopy(machines_dict)
    
    # Estrategia mejorada: Priorizar OTs urgentes, agrupando por producto cuando es posible
    # Agrupar tareas por producto
    products_tasks: Dict[str, List[ProductTask]] = {}
    for task in tasks:
        if task.product not in products_tasks:
            products_tasks[task.product] = []
        products_tasks[task.product].append(task)
    
    # Separar tareas urgentes (due <= 40h) de no urgentes
    urgent_tasks_by_product: Dict[str, List[ProductTask]] = {}
    normal_tasks_by_product: Dict[str, List[ProductTask]] = {}
    
    for product, product_tasks in products_tasks.items():
        urgent_tasks_by_product[product] = [t for t in product_tasks if t.ot_due <= 40]
        normal_tasks_by_product[product] = [t for t in product_tasks if t.ot_due > 40]
    
    # Ordenar productos por urgencia (fecha límite más temprana de tareas urgentes)
    product_deadlines: Dict[str, float] = {}
    for product in products_tasks:
        product_deadlines[product] = calcular_fecha_limite_producto(product, tasks)
    
    products_sorted = sorted(
        products_tasks.keys(),
        key=lambda p: product_deadlines[p]
    )
    
    schedule = []
    ot_completion_times: Dict[str, float] = {}  # {ot_id: tiempo_completacion}
    ot_products_produced: Dict[str, Dict[str, int]] = {}  # {ot_id: {product: cantidad_producida}}
    
    # Inicializar tracking de OTs
    for ot in orders:
        ot_completion_times[ot.id] = 0.0
        ot_products_produced[ot.id] = {p: 0 for p in ot.get_products().keys()}
    
    # FASE 1: Procesar tareas urgentes primero (priorizando completar OTs a tiempo)
    for product in products_sorted:
        urgent_tasks = urgent_tasks_by_product.get(product, [])
        if not urgent_tasks:
            continue
        
        urgent_qty = sum(t.quantity for t in urgent_tasks)
        assignments, _ = evaluar_distribucion_paralela(
            product, urgent_qty, machines, setup_times_dict, default_setup
        )
        
        production_ends = []
        urgent_ot_ids = [t.ot_id for t in urgent_tasks]
        
        for m_name, qty, start_time, end_time, setup_time in assignments:
            machine_available = machines[m_name].available_at
            
            if setup_time > 0:
                setup_start = machine_available
                setup_end = setup_start + setup_time
                schedule.append(ScheduleItem(
                    type="SETUP",
                    machine=m_name,
                    start=setup_start,
                    end=setup_end,
                    duration=setup_time,
                    format=product,
                    color="#808080"
                ))
                production_start = setup_end
            else:
                production_start = machine_available
            
            production_end = production_start + (qty / machines[m_name].capacity)
            production_ends.append(production_end)
            
            all_on_time = all(production_end <= t.ot_due for t in urgent_tasks)
            
            schedule.append(ScheduleItem(
                type="PRODUCTION",
                machine=m_name,
                start=production_start,
                end=production_end,
                duration=production_end - production_start,
                product=product,
                quantity=qty,
                format=product,
                ot_ids=urgent_ot_ids,
                color="#4A90E2",
                on_time=all_on_time
            ))
            
            machines[m_name].available_at = production_end
            machines[m_name].last_format = product
        
        # Actualizar tracking para OTs urgentes
        max_production_end = max(production_ends) if production_ends else 0
        for task in urgent_tasks:
            ot_products_produced[task.ot_id][product] += task.quantity
            if all(ot_products_produced[task.ot_id][p] >= ot_products[task.ot_id][p] 
                   for p in ot_products[task.ot_id]):
                ot_completion_times[task.ot_id] = max(
                    ot_completion_times[task.ot_id],
                    max_production_end
                )
    
    # FASE 2: Procesar tareas no urgentes (pueden agruparse completamente)
    for product in products_sorted:
        normal_tasks = normal_tasks_by_product.get(product, [])
        if not normal_tasks:
            continue
        
        normal_qty = sum(t.quantity for t in normal_tasks)
        assignments, _ = evaluar_distribucion_paralela(
            product, normal_qty, machines, setup_times_dict, default_setup
        )
        
        production_ends = []
        normal_ot_ids = [t.ot_id for t in normal_tasks]
        
        for m_name, qty, start_time, end_time, setup_time in assignments:
            machine_available = machines[m_name].available_at
            
            # Verificar si necesita setup (puede que ya esté configurada para este producto)
            if machines[m_name].last_format != product:
                actual_setup_time = calcular_setup_time(
                    machines[m_name].last_format,
                    product,
                    setup_times_dict,
                    default_setup
                )
            else:
                actual_setup_time = 0
            
            if actual_setup_time > 0:
                setup_start = machine_available
                setup_end = setup_start + actual_setup_time
                schedule.append(ScheduleItem(
                    type="SETUP",
                    machine=m_name,
                    start=setup_start,
                    end=setup_end,
                    duration=actual_setup_time,
                    format=product,
                    color="#808080"
                ))
                production_start = setup_end
            else:
                production_start = machine_available
            
            production_end = production_start + (qty / machines[m_name].capacity)
            production_ends.append(production_end)
            
            all_on_time = all(production_end <= t.ot_due for t in normal_tasks)
            
            schedule.append(ScheduleItem(
                type="PRODUCTION",
                machine=m_name,
                start=production_start,
                end=production_end,
                duration=production_end - production_start,
                product=product,
                quantity=qty,
                format=product,
                ot_ids=normal_ot_ids,
                color="#4A90E2",
                on_time=all_on_time
            ))
            
            machines[m_name].available_at = production_end
            machines[m_name].last_format = product
        
        # Actualizar tracking para OTs no urgentes
        max_production_end = max(production_ends) if production_ends else 0
        for task in normal_tasks:
            ot_products_produced[task.ot_id][product] += task.quantity
            if all(ot_products_produced[task.ot_id][p] >= ot_products[task.ot_id][p] 
                   for p in ot_products[task.ot_id]):
                ot_completion_times[task.ot_id] = max(
                    ot_completion_times[task.ot_id],
                    max_production_end
                )
    
    # Calcular resumen estadístico
    total_ots = len(orders)
    total_setups = len([s for s in schedule if s.type == "SETUP"])
    total_horas = max([s.end for s in schedule], default=0)
    
    # Calcular cantidad total producida
    qty_total_cliente = sum(
        sum(ot_products[ot.id].values()) for ot in orders
    )
    
    # Calcular atrasos (ya no rechazamos, solo reportamos)
    atrasos = []
    for ot in orders:
        completion_time = ot_completion_times[ot.id]
        if completion_time > ot.due:
            atrasos.append({
                "ot_id": ot.id,
                "atraso_horas": completion_time - ot.due,
                "cluster": ot.cluster,
                "due": ot.due,
                "completion": completion_time
            })
    
    summary = {
        "total_ots": total_ots,
        "total_setups": total_setups,
        "total_horas": round(total_horas, 2),
        "qty_total_cliente": qty_total_cliente,
        "qty_total_extra": 0,  # No hay producción extra en el nuevo modelo
        "atrasos": atrasos,  # Siempre incluimos atrasos, incluso si está vacío
        "horizonte_usado": 0
    }
    
    # Agrupar por máquina
    schedule_by_machine: Dict[str, List[ScheduleItem]] = {}
    for task in schedule:
        machine = task.machine
        if machine:
            if machine not in schedule_by_machine:
                schedule_by_machine[machine] = []
            schedule_by_machine[machine].append(task)
    
    # Ordenar tareas dentro de cada máquina
    for machine in schedule_by_machine:
        schedule_by_machine[machine].sort(key=lambda x: x.start)
    
    return schedule, schedule_by_machine, summary

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
        # Obtener productos (compatibilidad con ambos formatos)
        try:
            products = ot.get_products()
            if len(products) > 1:
                # Si tiene múltiples productos, no debería estar aquí (debería usar algoritmo optimizado)
                # Pero por seguridad, usar el primer producto
                format_ot = list(products.keys())[0]
                qty_ot = products[format_ot]
            else:
                format_ot = list(products.keys())[0] if products else ot.format
                qty_ot = list(products.values())[0] if products else ot.qty
        except:
            # Formato antiguo
            format_ot = ot.format
            qty_ot = ot.qty
        
        futuras = futuras_mismo_formato(ot, orders_sorted, horizonte)
        extra_qty = conviene_aprovechar(ot, futuras, horizonte, costo_inv)
        total_qty = qty_ot + extra_qty

        best_machine = None
        best_end = None
        best_setup = 0

        for m_name, machine_data in machines.items():
            st = calcular_setup_time(
                machine_data.last_format,
                format_ot,
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
                format=format_ot,
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
            qty_cliente=qty_ot,
            qty_extra=extra_qty,
            format=format_ot,
            color="#4A90E2",  # Azul claro para producción
            on_time=on_time
        ))

        machines[best_machine].available_at = best_end
        machines[best_machine].last_format = format_ot

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
            "/api/schedule": "POST - Programa la producción",
            "/api/health": "GET - Verificar salud de la API",
            "/docs": "Documentación interactiva (Swagger UI)",
            "/redoc": "Documentación alternativa (ReDoc)"
        }
    }

@api_router.post("/schedule", response_model=ScheduleResponse)
def crear_programa(request: ScheduleRequest):
    """
    Endpoint principal que recibe las órdenes de trabajo y máquinas,
    y devuelve el programa de producción optimizado.
    
    Detecta automáticamente si las OTs tienen múltiples productos y usa
    el algoritmo optimizado correspondiente.
    """
    try:
        # Detectar si alguna OT tiene múltiples productos
        usar_optimizado = False
        for ot in request.orders:
            try:
                products = ot.get_products()
                if len(products) > 1:
                    usar_optimizado = True
                    break
            except:
                # Si no puede obtener productos, usar formato antiguo
                pass
        
        # Usar algoritmo optimizado si hay OTs con múltiples productos
        if usar_optimizado:
            schedule, schedule_by_machine, summary = programar_produccion_optimizada(
                orders=request.orders,
                machines_dict=request.machines,
                setup_times=request.setup_times,
                default_setup=request.default_setup_time
            )
        else:
            # Usar algoritmo original para compatibilidad
            schedule, schedule_by_machine, summary = programar_produccion(
                orders=request.orders,
                machines_dict=request.machines,
                setup_times=request.setup_times,
                horizonte=request.horizonte_aprovechamiento,
                costo_inv=request.costo_inventario_unitario,
                default_setup=request.default_setup_time
            )
        
        # Calcular fechas/horas reales si se proporcionó fecha de inicio
        if request.start_datetime:
            try:
                fecha_inicio = datetime.fromisoformat(request.start_datetime.replace('Z', '+00:00'))
            except:
                fecha_inicio = datetime.now()
        else:
            fecha_inicio = datetime.now()
        
        # Agregar información de fecha/hora a cada tarea
        for task in schedule:
            start_dt = horas_a_fecha_hora(
                task.start,
                fecha_inicio,
                request.work_hours_per_day,
                request.work_start_hour,
                request.work_days
            )
            end_dt = horas_a_fecha_hora(
                task.end,
                fecha_inicio,
                request.work_hours_per_day,
                request.work_start_hour,
                request.work_days
            )
            task.start_datetime_str = formatear_fecha_hora(start_dt)
            task.end_datetime_str = formatear_fecha_hora(end_dt)
        
        # También agregar a schedule_by_machine (son las mismas referencias)
        
        # Generar logs formateados
        logs = generar_logs(schedule, schedule_by_machine, summary)
        
        return ScheduleResponse(
            schedule=schedule,
            schedule_by_machine=schedule_by_machine,
            summary=summary,
            logs=logs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el programa: {str(e)}")

@api_router.get("/health")
def health_check():
    """Endpoint de salud para verificar que la API está funcionando"""
    return {"status": "healthy"}

# Incluir el router en la aplicación
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

