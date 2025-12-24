import matplotlib.pyplot as plt

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

HORIZONTE_APROVECHAMIENTO = 12   # horas futuras
COSTO_INVENTARIO_UNITARIO = 0.002  # costo ficticio por unidad/hora

# =====================================================
# DATOS FICTICIOS – ÓRDENES DE TRABAJO
# =====================================================

orders = [
    {"id": "OT1001", "due": 12, "qty": 800,  "cluster": 5, "format": "A"},
    {"id": "OT1002", "due": 18, "qty": 500,  "cluster": 4, "format": "B"},
    {"id": "OT1003", "due": 20, "qty": 700,  "cluster": 3, "format": "A"},
    {"id": "OT1004", "due": 28, "qty": 1200, "cluster": 2, "format": "C"},
    {"id": "OT1005", "due": 30, "qty": 600,  "cluster": 4, "format": "B"},
    {"id": "OT1006", "due": 40, "qty": 1500, "cluster": 1, "format": "A"},
    {"id": "OT1007", "due": 45, "qty": 900,  "cluster": 2, "format": "C"},
]

# =====================================================
# MÁQUINAS
# =====================================================

machines = {
    "Linea_1": {"capacity": 120, "available_at": 0, "last_format": None},
    "Linea_2": {"capacity": 90,  "available_at": 0, "last_format": None},
}

# =====================================================
# TIEMPOS DE SETUP (horas)
# =====================================================

SETUP_TIME = {
    ("A", "B"): 1.5, ("B", "A"): 1.5,
    ("A", "C"): 2.0, ("C", "A"): 2.0,
    ("B", "C"): 1.0, ("C", "B"): 1.0,
}

def setup(prev_fmt, new_fmt):
    if prev_fmt is None or prev_fmt == new_fmt:
        return 0
    return SETUP_TIME.get((prev_fmt, new_fmt), 1.5)

# =====================================================
# FUNCIONES CLAVE
# =====================================================

def prioridad(ot):
    return ot["due"] / ot["cluster"]

def futuras_mismo_formato(ot_actual, todas):
    return [
        o for o in todas
        if o["format"] == ot_actual["format"]
        and o["due"] > ot_actual["due"]
        and o["due"] <= ot_actual["due"] + HORIZONTE_APROVECHAMIENTO
    ]

def conviene_aprovechar(ot, futuras):
    if not futuras:
        return 0

    qty_futura = sum(o["qty"] for o in futuras)
    ahorro_setup = 1.5  # horas promedio evitadas
    costo_inv = qty_futura * COSTO_INVENTARIO_UNITARIO * HORIZONTE_APROVECHAMIENTO

    if ahorro_setup > costo_inv:
        return int(qty_futura * 0.5)  # producimos 50% adelantado
    return 0

# =====================================================
# ALGORITMO DE PROGRAMACIÓN
# =====================================================

orders_sorted = sorted(orders, key=prioridad)
schedule = []

for ot in orders_sorted:
    futuras = futuras_mismo_formato(ot, orders_sorted)
    extra_qty = conviene_aprovechar(ot, futuras)
    total_qty = ot["qty"] + extra_qty

    best_machine = None
    best_end = None
    best_setup = 0

    for m, data in machines.items():
        st = setup(data["last_format"], ot["format"])
        duration = total_qty / data["capacity"]
        end_time = data["available_at"] + st + duration

        if best_end is None or end_time < best_end:
            best_end = end_time
            best_machine = m
            best_setup = st

    start_time = machines[best_machine]["available_at"]

    if best_setup > 0:
        schedule.append({
            "type": "SETUP",
            "machine": best_machine,
            "start": start_time,
            "end": start_time + best_setup
        })
        start_time += best_setup

    schedule.append({
        "type": "OT",
        "id": ot["id"],
        "machine": best_machine,
        "start": start_time,
        "end": best_end,
        "due": ot["due"],
        "qty_cliente": ot["qty"],
        "qty_extra": extra_qty,
        "format": ot["format"]
    })

    machines[best_machine]["available_at"] = best_end
    machines[best_machine]["last_format"] = ot["format"]

# =====================================================
# SALIDA CONSOLA (para backend / debug)
# =====================================================

print("\n=== PROGRAMA DE PRODUCCIÓN ===\n")

for task in schedule:
    if task["type"] == "SETUP":
        print(f"[{task['machine']}] SETUP {task['start']:.1f} → {task['end']:.1f}")
    else:
        print(
            f"[{task['machine']}] {task['id']} | "
            f"{task['start']:.1f} → {task['end']:.1f} | "
            f"Fmt {task['format']} | "
            f"Cliente {task['qty_cliente']} | "
            f"Extra {task['qty_extra']}"
        )

# =====================================================
# GRÁFICO TIPO GOOGLE CALENDAR
# =====================================================

fig, ax = plt.subplots(figsize=(14, 6))

for t in schedule:
    if t["type"] == "SETUP":
        ax.barh(t["machine"], t["end"] - t["start"], left=t["start"], color="gray")
    else:
        ax.barh(t["machine"], t["end"] - t["start"], left=t["start"])
        ax.text(t["start"] + 0.2, t["machine"], t["id"], va="center", fontsize=9)
        ax.axvline(t["due"], linestyle="--", alpha=0.25)

ax.set_title("Programa Diario de Producción – Vista tipo Google Calendar")
ax.set_xlabel("Horas")
ax.set_ylabel("Máquina")

plt.tight_layout()
plt.show()
