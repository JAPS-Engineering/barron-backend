# Modelo de Programación de Producción - Documentación Técnica

## 1. Introducción

Este documento describe el modelo heurístico de programación de producción implementado en la API. El modelo resuelve un problema de **Job Shop Scheduling** con **máquinas paralelas no idénticas**, considerando **setups dependientes de secuencia** y permitiendo **producción anticipada** para aprovechar rollos completos.

### 1.1 Clasificación del Problema

- **Tipo**: Job Shop Scheduling con máquinas paralelas
- **Características**:
  - Máquinas paralelas no idénticas (diferentes capacidades)
  - Setups dependientes de secuencia (cambio de formato)
  - Producción anticipada permitida (make-to-stock parcial)
  - Prioridades ponderadas (cluster comercial)
- **Método de resolución**: Heurística determinística basada en reglas de despacho
- **Complejidad**: O(n²·m) donde n = número de OT y m = número de máquinas

---

## 2. Parámetros del Modelo

### 2.1 Parámetros Globales

| Parámetro | Símbolo | Tipo | Descripción |
|-----------|---------|------|-------------|
| `HORIZONTE_APROVECHAMIENTO` | H | ℝ⁺ | Ventana temporal futura (horas) dentro de la cual se permite producir adelantado |
| `COSTO_INVENTARIO_UNITARIO` | c_inv | ℝ⁺ | Costo ficticio por unidad y hora de mantener stock (controla agresividad del aprovechamiento) |
| `DEFAULT_SETUP_TIME` | t_setup_default | ℝ⁺ | Tiempo de setup por defecto cuando no se especifica la combinación de formatos |

**Valores por defecto:**
- H = 12 horas
- c_inv = 0.002 unidades monetarias / (unidad × hora)

### 2.2 Parámetros de Entrada: Órdenes de Trabajo (OT)

Cada orden de trabajo i se define como:

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
- qty_i: cantidad solicitada de OT_i
- cluster_i: prioridad comercial de OT_i
- format_i: formato de OT_i

### 2.3 Parámetros de Entrada: Máquinas

Cada máquina j se define como:

```
M_j = {
  capacity: unidades producidas por hora (ℝ⁺)
  available_at: reloj interno de la máquina (ℝ⁺)
  last_format: último formato producido (string | null)
}
```

**Notación matemática:**
- j ∈ J = {1, 2, ..., m} donde m es el número de máquinas
- cap_j: capacidad de la máquina j (unidades/hora)
- t_available_j: tiempo disponible de la máquina j (horas)
- format_prev_j: último formato producido en máquina j

### 2.4 Parámetros: Matriz de Tiempos de Setup

Matriz de tiempos de setup entre formatos:

```
SETUP_TIME[format_a, format_b] = tiempo en horas
```

**Notación matemática:**
- t_setup(f_a, f_b): tiempo de setup para cambiar de formato f_a a f_b
- Si f_a = f_b o f_a = null: t_setup = 0
- Si (f_a, f_b) no existe en la matriz: t_setup = DEFAULT_SETUP_TIME

---

## 3. Variables de Decisión

### 3.1 Variables Principales

| Variable | Símbolo | Tipo | Descripción |
|----------|---------|------|-------------|
| Asignación de OT a máquina | x_{i,j} | {0,1} | 1 si OT_i se asigna a máquina j, 0 en caso contrario |
| Cantidad extra producida | qty_extra_i | ℤ⁺ | Cantidad adicional producida para OT_i (aprovechamiento de rollo) |
| Hora de inicio | start_i | ℝ⁺ | Hora de inicio de producción de OT_i |
| Hora de fin | end_i | ℝ⁺ | Hora de fin de producción de OT_i |
| Tiempo de setup | t_setup_i | ℝ⁺ | Tiempo de setup necesario antes de OT_i |

### 3.2 Variables Derivadas

- **Cantidad total a producir**: Q_i = qty_i + qty_extra_i
- **Duración de producción**: dur_i = Q_i / cap_j (donde j es la máquina asignada)
- **Prioridad calculada**: prioridad_i = due_i / cluster_i

---

## 4. Restricciones del Modelo

### 4.1 Restricciones de Asignación

**R1: Cada OT se asigna a exactamente una máquina**

```
∑_{j∈J} x_{i,j} = 1    ∀i ∈ I
```

Cada orden de trabajo debe ser procesada en una y solo una máquina.

### 4.2 Restricciones de Secuencia y Capacidad

**R2: No hay solapamiento en una máquina**

Para cada máquina j, las OT asignadas deben ordenarse secuencialmente sin solapamiento:

```
end_i ≤ start_k    ∀i,k ∈ I_j, i ≠ k
```

donde I_j = {i ∈ I : x_{i,j} = 1} es el conjunto de OT asignadas a la máquina j.

**R3: Setups obligatorios si cambia el formato**

Si una OT_i se asigna a máquina j y el formato cambia respecto al último formato:

```
t_setup_i = t_setup(format_prev_j, format_i)    si format_prev_j ≠ format_i
t_setup_i = 0                                    si format_prev_j = format_i o format_prev_j = null
```

**R4: Relación entre tiempos**

Para cada OT_i asignada a máquina j:

```
start_i ≥ t_available_j + t_setup_i
end_i = start_i + (Q_i / cap_j)
t_available_j = max{end_k : x_{k,j} = 1}    (actualizado después de cada asignación)
```

### 4.3 Restricciones de Producción Anticipada

**R5: Aprovechamiento de rollo solo en condiciones seguras**

La cantidad extra qty_extra_i > 0 solo si:

1. **Existencia de OT futuras compatibles**:
   ```
   ∃k ∈ I : format_k = format_i ∧ due_k > due_i ∧ due_k ≤ due_i + H
   ```

2. **Criterio económico**: El ahorro de setup debe superar el costo de inventario
   ```
   ahorro_setup > costo_inventario
   ```
   
   donde:
   - `ahorro_setup ≈ t_setup_promedio` (horas promedio evitadas ≈ 1.5h)
   - `costo_inventario = qty_extra_i × c_inv × H`

3. **Límite práctico**: qty_extra_i ≤ 0.5 × ∑_{k futuras compatibles} qty_k

---

## 5. Función Objetivo

Aunque el algoritmo es heurístico (no resuelve un optimizador exacto), el modelo busca **minimizar implícitamente**:

### 5.1 Función Objetivo Compuesta

```
Minimizar: Z = w₁ × Tardanza + w₂ × Setup + w₃ × Inventario
```

donde:

1. **Tardanza Ponderada**:
   ```
   Tardanza = ∑_{i∈I} cluster_i × max(0, end_i - due_i)
   ```
   - Penaliza los atrasos ponderados por importancia comercial
   - OT con cluster alto tienen mayor penalización

2. **Tiempo Total de Setup**:
   ```
   Setup = ∑_{i∈I} t_setup_i
   ```
   - Minimiza los tiempos muertos por cambio de formato

3. **Costo de Inventario**:
   ```
   Inventario = ∑_{i∈I} qty_extra_i × c_inv × H
   ```
   - Penaliza el inventario innecesario generado por producción anticipada

### 5.2 Estrategia Heurística

En lugar de resolver el problema de optimización exacta (MILP), el algoritmo utiliza una **heurística de despacho** que toma decisiones locales:

1. **Ordenamiento**: Ordena OT por prioridad ascendente (due_i / cluster_i)
2. **Para cada OT**:
   - Calcula qty_extra_i usando función `conviene_aprovechar()`
   - Evalúa cada máquina j calculando: `end_time_j = t_available_j + t_setup_i + (Q_i / cap_j)`
   - Selecciona la máquina que minimiza `end_time_j` (termina antes)
3. **Actualización**: Actualiza el estado de la máquina asignada

Esta estrategia es **greedy** pero eficiente para recálculo frecuente (cada hora).

---

## 6. Algoritmo: Flujo de Ejecución

### 6.1 Pseudocódigo

```
1. INICIALIZACIÓN
   - Ordenar OT por prioridad: prioridad_i = due_i / cluster_i
   - Inicializar máquinas: t_available_j = 0, format_prev_j = null

2. PARA CADA OT_i (en orden de prioridad):
   
   a) DECISIÓN DE CANTIDAD EXTRA:
      futuras = {k ∈ I : format_k = format_i ∧ due_k > due_i ∧ due_k ≤ due_i + H}
      SI conviene_aprovechar(OT_i, futuras):
         qty_extra_i = 0.5 × ∑_{k∈futuras} qty_k
      SINO:
         qty_extra_i = 0
      
      Q_i = qty_i + qty_extra_i
   
   b) EVALUACIÓN DE MÁQUINAS:
      PARA CADA máquina j:
         t_setup_i = calcular_setup(format_prev_j, format_i)
         dur_i = Q_i / cap_j
         end_time_j = t_available_j + t_setup_i + dur_i
      
      Seleccionar j* = argmin_{j∈J} end_time_j
   
   c) ASIGNACIÓN Y ACTUALIZACIÓN:
      SI t_setup_i > 0:
         Agregar bloque SETUP: [t_available_j*, t_available_j* + t_setup_i]
      
      Agregar bloque OT: [t_available_j* + t_setup_i, end_time_j*]
      
      t_available_j* = end_time_j*
      format_prev_j* = format_i

3. RESULTADO:
   - schedule: lista de bloques (SETUP/OT) con start, end, máquina
   - schedule_by_machine: agrupado por máquina para visualización
```

### 6.2 Funciones Auxiliares

#### `prioridad(OT_i)`
```python
return due_i / cluster_i
```

#### `futuras_mismo_formato(OT_i, I, H)`
```python
return [k for k in I 
        if format_k == format_i 
        and due_k > due_i 
        and due_k <= due_i + H]
```

#### `conviene_aprovechar(OT_i, futuras, H, c_inv)`
```python
SI futuras está vacío:
    return 0

qty_futura = sum(qty_k for k in futuras)
ahorro_setup = 1.5  # horas promedio evitadas
costo_inv = qty_futura × c_inv × H

SI ahorro_setup > costo_inv:
    return int(qty_futura × 0.5)  # 50% adelantado
SINO:
    return 0
```

#### `calcular_setup(format_prev, format_new, SETUP_TIME, default)`
```python
SI format_prev == null O format_prev == format_new:
    return 0
SINO:
    return SETUP_TIME.get((format_prev, format_new), default)
```

---

## 7. Complejidad Computacional

- **Ordenamiento de OT**: O(n log n)
- **Para cada OT** (n iteraciones):
  - Búsqueda de futuras: O(n)
  - Evaluación de máquinas: O(m)
  - Asignación: O(1)
- **Complejidad total**: **O(n² + n·m)**

Para n = 100 OT y m = 10 máquinas: ~11,000 operaciones → **tiempo de ejecución < 1 segundo**

---

## 8. Extensiones Futuras

El modelo actual no incluye (pero está diseñado para crecer hacia):

1. **Validación de stock de materia prima**
2. **Manejo de turnos y paradas programadas**
3. **Optimización exacta** (MILP/MIP solver)
4. **Reprogramación automática** ante eventos (máquinas fuera de servicio, nuevas OT urgentes)
5. **Restricciones de recursos compartidos** (operadores, herramientas)
6. **Optimización multi-objetivo** con pesos configurables

---

## 9. Referencias y Notación

### Símbolos Utilizados

| Símbolo | Significado |
|---------|-------------|
| I | Conjunto de órdenes de trabajo (OT) |
| J | Conjunto de máquinas |
| n | Número de OT |
| m | Número de máquinas |
| H | Horizonte de aprovechamiento |
| c_inv | Costo de inventario unitario |
| ℝ⁺ | Números reales positivos |
| ℤ⁺ | Enteros positivos |
| {0,1} | Variable binaria |

### Convenciones

- Los tiempos están en **horas** (número decimal)
- Las cantidades están en **unidades** (enteros)
- La fecha compromiso (`due`) es relativa a "ahora" = 0
- Los formatos son identificadores de texto (ej: "A", "B", "C")

---

## 10. Ejemplo Numérico

### Datos de Entrada

**OT1**: due=12, qty=800, cluster=5, format="A"
**OT2**: due=18, qty=500, cluster=4, format="B"
**Máquina 1**: cap=120 unidades/hora

### Cálculo de Prioridad

- prioridad_1 = 12/5 = 2.4
- prioridad_2 = 18/4 = 4.5

**Orden**: OT1 primero (menor prioridad = más urgente)

### Asignación de OT1 a Máquina 1

1. **Cantidad extra**: No hay OT futuras compatibles → qty_extra = 0
2. **Setup**: format_prev = null → t_setup = 0
3. **Duración**: dur = 800/120 = 6.67 horas
4. **Fin**: end = 0 + 0 + 6.67 = 6.67 horas
5. **Actualización**: t_available_1 = 6.67, format_prev_1 = "A"

### Asignación de OT2 a Máquina 1

1. **Cantidad extra**: 0 (no hay futuras)
2. **Setup**: format_prev="A", format_new="B" → t_setup = 1.5 horas
3. **Duración**: dur = 500/120 = 4.17 horas
4. **Fin**: end = 6.67 + 1.5 + 4.17 = 12.34 horas
5. **Estado final**: t_available_1 = 12.34, format_prev_1 = "B"

**Resultado**: OT1 termina a las 6.67h (antes de due=12h) ✅, OT2 termina a las 12.34h (antes de due=18h) ✅

