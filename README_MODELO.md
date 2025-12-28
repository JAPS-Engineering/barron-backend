# Modelo de Programación de Producción - Documentación Técnica

## 1. Introducción

Este documento describe el modelo heurístico de programación de producción implementado en la API. El modelo resuelve un problema de **Job Shop Scheduling** con **máquinas paralelas no idénticas**, considerando **setups dependientes de secuencia** y permitiendo **OTs con múltiples productos**.

### 1.1 Clasificación del Problema

- **Tipo**: Job Shop Scheduling con máquinas paralelas
- **Características**:
  - Máquinas paralelas no idénticas (diferentes capacidades)
  - Setups dependientes de secuencia (cambio de formato/producto)
  - OTs con múltiples productos (cada OT puede requerir varios tipos de productos)
  - Producción agrupada por producto para minimizar setups
  - Distribución paralela entre máquinas para minimizar makespan
  - Prioridades ponderadas (cluster comercial)
- **Método de resolución**: Heurística determinística con estrategia de dos fases
- **Complejidad**: O(n·p·m) donde n = número de OTs, p = número de productos únicos, m = número de máquinas

### 1.2 Objetivos del Modelo

1. **Minimizar atrasos**: Priorizar OTs urgentes para completarlas a tiempo
2. **Minimizar makespan**: Reducir el tiempo total de producción mediante paralelismo
3. **Minimizar setups**: Agrupar producción del mismo producto para reducir cambios de configuración
4. **Manejo de factibilidad**: Si no es posible completar todas las OTs a tiempo, optimizar para minimizar el número de atrasos

---

## 2. Parámetros del Modelo

### 2.1 Parámetros Globales

| Parámetro | Símbolo | Tipo | Descripción |
|-----------|---------|------|-------------|
| `HORIZONTE_APROVECHAMIENTO` | H | ℝ⁺ | Ventana temporal futura (horas) dentro de la cual se permite producir adelantado (compatibilidad con formato antiguo) |
| `COSTO_INVENTARIO_UNITARIO` | c_inv | ℝ⁺ | Costo ficticio por unidad y hora de mantener stock (compatibilidad con formato antiguo) |
| `DEFAULT_SETUP_TIME` | t_setup_default | ℝ⁺ | Tiempo de setup por defecto cuando no se especifica la combinación de formatos |

**Valores por defecto:**
- H = 12 horas
- c_inv = 0.002 unidades monetarias / (unidad × hora)
- t_setup_default = 1.5 horas

### 2.2 Parámetros de Entrada: Órdenes de Trabajo (OT)

Cada orden de trabajo i se define como:

**Formato Nuevo (Optimizado - Múltiples Productos):**
```
OT_i = {
  id: identificador único (string)
  due: fecha compromiso en horas desde "ahora" (ℝ⁺)
  cluster: prioridad comercial (ℤ⁺, mayor = más importante)
  products: diccionario de productos y cantidades {producto: cantidad}
}
```

**Formato Antiguo (Compatibilidad - Un Solo Producto):**
```
OT_i = {
  id: identificador único (string)
  due: fecha compromiso en horas desde "ahora" (ℝ⁺)
  qty: cantidad solicitada por el cliente (ℤ⁺)
  cluster: prioridad comercial (ℤ⁺, mayor = más importante)
  format: formato/cuchillo/dimensión (string)
}
```

**Notación matemática:**
- i ∈ I = {1, 2, ..., n} donde n es el número de OT
- due_i: fecha compromiso de OT_i
- cluster_i: prioridad comercial de OT_i
- products_i: diccionario {p: qty_p} donde p es un producto y qty_p es la cantidad requerida
- Para formato antiguo: qty_i, format_i

**Ejemplo:**
```json
{
  "id": "OT0",
  "due": 20,
  "cluster": 5,
  "products": {"A": 200, "B": 300}  // OT0 requiere 200 unidades de A y 300 de B
}
```

### 2.3 Parámetros de Entrada: Máquinas

Cada máquina j se define como:

```
M_j = {
  capacity: unidades producidas por hora (ℝ⁺)
  available_at: reloj interno de la máquina (ℝ⁺)
  last_format: último formato/producto producido (string | null)
}
```

**Notación matemática:**
- j ∈ J = {1, 2, ..., m} donde m es el número de máquinas
- cap_j: capacidad de la máquina j (unidades/hora)
- t_available_j: tiempo disponible de la máquina j (horas)
- format_prev_j: último formato/producto producido en máquina j

### 2.4 Parámetros: Matriz de Tiempos de Setup

Matriz de tiempos de setup entre productos:

```
SETUP_TIME[producto_a, producto_b] = tiempo en horas
```

**Notación matemática:**
- t_setup(p_a, p_b): tiempo de setup para cambiar de producto p_a a p_b
- Si p_a = p_b o p_a = null: t_setup = 0
- Si (p_a, p_b) no existe en la matriz: t_setup = DEFAULT_SETUP_TIME

---

## 3. Variables de Decisión

### 3.1 Variables Principales

| Variable | Símbolo | Tipo | Descripción |
|----------|---------|------|-------------|
| Asignación de producción a máquina | x_{p,j} | {0,1} | 1 si producción de producto p se asigna a máquina j, 0 en caso contrario |
| Cantidad de producto p en máquina j | qty_{p,j} | ℤ⁺ | Cantidad de producto p producida en máquina j |
| Hora de inicio de producción | start_{p,j} | ℝ⁺ | Hora de inicio de producción de producto p en máquina j |
| Hora de fin de producción | end_{p,j} | ℝ⁺ | Hora de fin de producción de producto p en máquina j |
| Tiempo de setup | t_setup_{p,j} | ℝ⁺ | Tiempo de setup necesario antes de producir producto p en máquina j |

### 3.2 Variables Derivadas

- **Cantidad total de producto p**: Q_p = ∑_{i∈I} qty_{i,p} donde qty_{i,p} es la cantidad de producto p requerida por OT_i
- **Duración de producción**: dur_{p,j} = qty_{p,j} / cap_j
- **Fecha límite de producto p**: due_p = min{due_i : OT_i requiere producto p}
- **Tiempo de completación de OT_i**: completion_i = max{end_{p,j} : producto p de OT_i se produce en máquina j}

---

## 4. Restricciones del Modelo

### 4.1 Restricciones de Asignación

**R1: Cada producto debe producirse en al menos una máquina**

```
∑_{j∈J} x_{p,j} ≥ 1    ∀p ∈ P
```

donde P es el conjunto de productos únicos requeridos.

**R2: La cantidad total producida debe satisfacer la demanda**

```
∑_{j∈J} qty_{p,j} ≥ Q_p    ∀p ∈ P
```

### 4.2 Restricciones de Secuencia y Capacidad

**R3: No hay solapamiento en una máquina**

Para cada máquina j, las producciones asignadas deben ordenarse secuencialmente sin solapamiento:

```
end_{p1,j} ≤ start_{p2,j}    ∀p1, p2 ∈ P_j, p1 ≠ p2
```

donde P_j = {p ∈ P : x_{p,j} = 1} es el conjunto de productos asignados a la máquina j.

**R4: Setups obligatorios si cambia el producto**

Si se produce producto p en máquina j y el producto cambia respecto al último producido:

```
t_setup_{p,j} = t_setup(format_prev_j, p)    si format_prev_j ≠ p
t_setup_{p,j} = 0                             si format_prev_j = p o format_prev_j = null
```

**R5: Relación entre tiempos**

Para cada producto p asignado a máquina j:

```
start_{p,j} ≥ t_available_j + t_setup_{p,j}
end_{p,j} = start_{p,j} + (qty_{p,j} / cap_j)
t_available_j = max{end_{p,j} : x_{p,j} = 1}    (actualizado después de cada asignación)
```

### 4.3 Restricciones de Completación de OTs

**R6: Una OT se completa cuando todos sus productos están producidos**

```
completion_i = max{end_{p,j} : producto p de OT_i se produce en máquina j}
```

**R7: Optimización de atrasos (soft constraint)**

El modelo busca minimizar:
- Número de OTs atrasadas: |{i ∈ I : completion_i > due_i}|
- Tardanza total ponderada: ∑_{i∈I} cluster_i × max(0, completion_i - due_i)

**Nota**: A diferencia de versiones anteriores, el modelo **no rechaza** si hay atrasos. En su lugar, optimiza para minimizarlos y siempre genera una planificación completa.

---

## 5. Función Objetivo

El algoritmo busca **minimizar**:

### 5.1 Función Objetivo Compuesta

```
Minimizar: Z = w₁ × Atrasos + w₂ × Makespan + w₃ × Setups
```

donde:

1. **Número de OTs Atrasadas** (prioridad máxima):
   ```
   Atrasos = |{i ∈ I : completion_i > due_i}|
   ```
   - Minimiza el número de OTs que no cumplen su fecha límite
   - Prioridad máxima: completar OTs urgentes a tiempo

2. **Makespan Total**:
   ```
   Makespan = max{end_{p,j} : p ∈ P, j ∈ J}
   ```
   - Minimiza el tiempo total de producción
   - Se logra mediante distribución paralela entre máquinas

3. **Tiempo Total de Setup**:
   ```
   Setups = ∑_{p∈P, j∈J} t_setup_{p,j}
   ```
   - Minimiza los tiempos muertos por cambio de producto
   - Se logra agrupando producción del mismo producto

### 5.2 Estrategia Heurística de Dos Fases

El algoritmo utiliza una **estrategia de dos fases** para balancear los objetivos:

**FASE 1: Procesamiento de OTs Urgentes (due ≤ 40h)**
- Agrupa productos requeridos por OTs urgentes
- Distribuye producción entre máquinas en paralelo
- Prioriza completar estas OTs a tiempo

**FASE 2: Procesamiento de OTs No Urgentes (due > 40h)**
- Agrupa completamente por producto para minimizar setups
- Distribuye producción entre máquinas en paralelo
- Optimiza makespan total

---

## 6. Algoritmo: Flujo de Ejecución

### 6.1 Pseudocódigo del Modelo Optimizado

```
1. INICIALIZACIÓN
   - Descomponer OTs en tareas de productos individuales
   - Agrupar tareas por producto
   - Calcular fecha límite de cada producto: due_p = min{due_i : OT_i requiere p}
   - Inicializar máquinas: t_available_j = 0, format_prev_j = null

2. SEPARACIÓN POR URGENCIA
   - Separar tareas urgentes (due_i ≤ 40h) de no urgentes (due_i > 40h)
   - Agrupar por producto dentro de cada categoría

3. FASE 1: PROCESAR PRODUCTOS URGENTES
   PARA CADA producto p (ordenado por due_p):
      a) Obtener tareas urgentes del producto: T_urgent = {t : t.product = p ∧ t.ot_due ≤ 40}
      b) Calcular cantidad total urgente: Q_urgent = ∑_{t∈T_urgent} t.quantity
      c) EVALUAR DISTRIBUCIÓN PARALELA:
         - Evaluar asignar todo a una máquina
         - Evaluar distribuir entre máquinas disponibles
         - Seleccionar opción que minimiza makespan
      d) ASIGNAR Y PROGRAMAR:
         PARA CADA máquina j en asignación seleccionada:
            - Programar setup si es necesario
            - Programar producción de cantidad asignada
            - Actualizar t_available_j y format_prev_j
      e) ACTUALIZAR TRACKING DE OTs:
         PARA CADA OT_i que requiere producto p:
            - Actualizar cantidad producida de p
            - Si OT_i está completa: actualizar completion_i

4. FASE 2: PROCESAR PRODUCTOS NO URGENTES
   PARA CADA producto p (ordenado por due_p):
      a) Obtener tareas no urgentes: T_normal = {t : t.product = p ∧ t.ot_due > 40}
      b) Calcular cantidad total: Q_normal = ∑_{t∈T_normal} t.quantity
      c) EVALUAR DISTRIBUCIÓN PARALELA (igual que Fase 1)
      d) ASIGNAR Y PROGRAMAR (igual que Fase 1)
      e) ACTUALIZAR TRACKING DE OTs (igual que Fase 1)

5. RESULTADO:
   - schedule: lista de bloques (SETUP/PRODUCTION) con start, end, máquina, producto, ot_ids
   - schedule_by_machine: agrupado por máquina para visualización
   - summary: resumen con atrasos detectados
```

### 6.2 Función de Distribución Paralela

La función `evaluar_distribucion_paralela()` evalúa dos opciones:

**Opción 1: Asignar todo a una máquina**
- Selecciona la máquina que puede completar antes
- Calcula: end_time = available_at + setup_time + (quantity / capacity)

**Opción 2: Distribuir entre máquinas en paralelo**
- Distribuye cantidad proporcionalmente a capacidad
- Ajusta para que todas terminen aproximadamente al mismo tiempo
- Calcula makespan paralelo: max{end_time_j : j ∈ J}

**Decisión**: Usa paralelo si:
- Hay al menos 2 máquinas disponibles
- El makespan paralelo es mejor o similar (dentro del 10%)
- O si la cantidad es grande (>1000 unidades), siempre distribuye

### 6.3 Funciones Auxiliares

#### `descomponer_ots_en_tareas(orders)`
```python
tasks = []
for ot in orders:
    for product, quantity in ot.get_products().items():
        tasks.append(ProductTask(
            product=product,
            quantity=quantity,
            ot_id=ot.id,
            ot_due=ot.due,
            ot_cluster=ot.cluster
        ))
return tasks, ot_products
```

#### `calcular_fecha_limite_producto(product, tasks)`
```python
product_tasks = [t for t in tasks if t.product == product]
return min(t.ot_due for t in product_tasks)
```

#### `evaluar_distribucion_paralela(product, quantity, machines, setup_times, default_setup)`
```python
# Evalúa asignación única vs. distribución paralela
# Retorna: (asignaciones, makespan)
# donde asignaciones = [(machine, qty, start, end, setup_time), ...]
```

#### `calcular_setup_time(prev_product, new_product, setup_times_dict, default)`
```python
SI prev_product == null O prev_product == new_product:
    return 0
SINO:
    key = f"{prev_product}-{new_product}"
    return setup_times_dict.get(key, default)
```

---

## 7. Complejidad Computacional

- **Descomposición de OTs**: O(n·p_avg) donde p_avg es el número promedio de productos por OT
- **Agrupación por producto**: O(n·p_avg)
- **Ordenamiento de productos**: O(p log p) donde p es el número de productos únicos
- **Para cada producto** (p iteraciones):
  - Evaluación de distribución paralela: O(m²)
  - Asignación y programación: O(m)
  - Actualización de tracking: O(n)
- **Complejidad total**: **O(n·p_avg + p·log p + p·(m² + n))**

Para n = 25 OTs, p = 3 productos, m = 2 máquinas: ~200 operaciones → **tiempo de ejecución < 0.1 segundos**

---

## 8. Estructura de Salida

### 8.1 ScheduleItem

Cada elemento del schedule puede ser de tipo:

**SETUP:**
```json
{
  "type": "SETUP",
  "machine": "Linea_1",
  "start": 0.0,
  "end": 1.5,
  "duration": 1.5,
  "format": "B",
  "color": "#808080"
}
```

**PRODUCTION:**
```json
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
}
```

### 8.2 Summary

```json
{
  "total_ots": 25,
  "total_setups": 4,
  "total_horas": 73.10,
  "qty_total_cliente": 13880,
  "qty_total_extra": 0,
  "atrasos": [
    {
      "ot_id": "OT6",
      "atraso_horas": 28.10,
      "cluster": 2,
      "due": 60.0,
      "completion": 88.10
    }
  ],
  "horizonte_usado": 0
}
```

---

## 9. Ventajas del Modelo Optimizado

1. **Manejo de OTs Complejas**: Soporta OTs que requieren múltiples productos
2. **Paralelismo Inteligente**: Distribuye producción entre máquinas para minimizar makespan
3. **Priorización de Urgencia**: Completa OTs urgentes primero
4. **Minimización de Setups**: Agrupa producción del mismo producto
5. **Robustez**: Siempre genera una planificación, incluso si hay atrasos
6. **Flexibilidad**: Compatible con formato antiguo (un producto por OT)

---

## 10. Extensiones Futuras

El modelo actual no incluye (pero está diseñado para crecer hacia):

1. **Validación de stock de materia prima**
2. **Manejo de turnos y paradas programadas**
3. **Optimización exacta** (MILP/MIP solver)
4. **Reprogramación automática** ante eventos (máquinas fuera de servicio, nuevas OT urgentes)
5. **Restricciones de recursos compartidos** (operadores, herramientas)
6. **Optimización multi-objetivo** con pesos configurables
7. **Algoritmos genéticos o simulated annealing** para mejor optimización global

---

## 11. Referencias y Notación

### Símbolos Utilizados

| Símbolo | Significado |
|---------|-------------|
| I | Conjunto de órdenes de trabajo (OT) |
| J | Conjunto de máquinas |
| P | Conjunto de productos únicos |
| n | Número de OT |
| m | Número de máquinas |
| p | Número de productos únicos |
| H | Horizonte de aprovechamiento |
| c_inv | Costo de inventario unitario |
| ℝ⁺ | Números reales positivos |
| ℤ⁺ | Enteros positivos |
| {0,1} | Variable binaria |

### Convenciones

- Los tiempos están en **horas** (número decimal)
- Las cantidades están en **unidades** (enteros)
- La fecha compromiso (`due`) es relativa a "ahora" = 0
- Los productos son identificadores de texto (ej: "A", "B", "C")
- Producción 24/7: no hay restricciones de horarios laborales

---

## 12. Ejemplo Numérico

### Datos de Entrada

**OT0**: due=20, cluster=5, products={"A": 200, "B": 300}
**OT1**: due=20, cluster=4, products={"B": 250, "C": 150}
**OT2**: due=20, cluster=3, products={"A": 180, "B": 200}
**Máquina 1**: cap=120 unidades/hora
**Máquina 2**: cap=90 unidades/hora

### Descomposición en Tareas

- Producto A: OT0 (200), OT2 (180) → Total: 380 unidades
- Producto B: OT0 (300), OT1 (250), OT2 (200) → Total: 750 unidades
- Producto C: OT1 (150) → Total: 150 unidades

### Fase 1: Procesamiento Urgente (due ≤ 40h)

**Producto A (urgente, due=20):**
- Cantidad: 380 unidades
- Distribución paralela:
  - Máquina 1: 230 unidades → 1.92h
  - Máquina 2: 150 unidades → 1.67h
- Makespan: 1.92h (ambas máquinas terminan casi simultáneamente)

**Producto B (urgente, due=20):**
- Cantidad: 750 unidades
- Setup necesario en ambas máquinas (cambio de A a B)
- Distribución paralela:
  - Máquina 1: 450 unidades → Setup 1.5h + Producción 3.75h = 5.25h
  - Máquina 2: 300 unidades → Setup 1.5h + Producción 3.33h = 4.83h
- Makespan: 5.25h

**Producto C (urgente, due=20):**
- Cantidad: 150 unidades
- Setup necesario
- Asignación: Máquina 2 (disponible antes)
- Tiempo: Setup 1.0h + Producción 1.67h = 2.67h

### Completación de OTs

- **OT0**: Se completa cuando terminan A y B → max(1.92h, 5.25h) = 5.25h ✅ (antes de due=20h)
- **OT1**: Se completa cuando terminan B y C → max(5.25h, 2.67h) = 5.25h ✅ (antes de due=20h)
- **OT2**: Se completa cuando terminan A y B → max(1.92h, 5.25h) = 5.25h ✅ (antes de due=20h)

**Resultado**: Todas las OTs se completan a tiempo, makespan total = 5.25h

---

## 13. Comparación con Modelo Anterior

| Característica | Modelo Anterior | Modelo Optimizado |
|----------------|-----------------|------------------|
| Productos por OT | 1 (format) | Múltiples (products dict) |
| Estrategia | Greedy por OT | Dos fases (urgentes/no urgentes) |
| Paralelismo | No | Sí (distribución entre máquinas) |
| Manejo de atrasos | Rechaza si no es factible | Optimiza para minimizar atrasos |
| Agrupación | Por OT individual | Por producto (minimiza setups) |
| Makespan | No optimizado | Minimizado mediante paralelismo |

---

## 14. Uso del Modelo

### 14.1 Formato de Request

```json
{
  "orders": [
    {
      "id": "OT0",
      "due": 20,
      "cluster": 5,
      "products": {"A": 200, "B": 300}
    }
  ],
  "machines": {
    "Linea_1": {"capacity": 120, "available_at": 0, "last_format": null},
    "Linea_2": {"capacity": 90, "available_at": 0, "last_format": null}
  },
  "setup_times": {
    "A-B": 1.5,
    "B-A": 1.5,
    "A-C": 2.0,
    "C-A": 2.0,
    "B-C": 1.0,
    "C-B": 1.0
  },
  "start_datetime": "2024-01-25T08:00:00",
  "work_hours_per_day": 24.0,
  "work_start_hour": 0,
  "work_days": [0, 1, 2, 3, 4, 5, 6]
}
```

### 14.2 Formato de Response

```json
{
  "schedule": [...],
  "schedule_by_machine": {...},
  "summary": {
    "total_ots": 25,
    "total_setups": 4,
    "total_horas": 73.10,
    "qty_total_cliente": 13880,
    "atrasos": [...]
  },
  "logs": [...]
}
```

---

## 15. Notas de Implementación

- El modelo detecta automáticamente si se usa formato nuevo (products) o antiguo (format + qty)
- La estrategia de dos fases usa un umbral de 40 horas para separar urgentes de no urgentes
- La distribución paralela solo se activa si reduce el makespan en al menos 5% o si la cantidad es >1000 unidades
- Los atrasos se reportan en el summary pero no impiden la generación de la planificación
