"""
Script para probar la API de programación de producción con datos de testeo
"""
import requests
import json
from datetime import datetime

# URL de la API
API_URL = "http://localhost:8000/api/schedule"

# Datos de testeo con OTs de múltiples productos (nuevo modelo optimizado)
# Mismos datos que se usan en el frontend
# Fechas límite ajustadas para ser realistas considerando makespan ~73 horas
datos_testeo_optimizado = {
    "orders": [
        # Día 1 - OTs urgentes con múltiples productos (completadas en ~16h)
        {"id": "OT0", "due": 20, "cluster": 5, "products": {"A": 200, "B": 300}},
        {"id": "OT1", "due": 20, "cluster": 4, "products": {"B": 250, "C": 150}},
        {"id": "OT2", "due": 20, "cluster": 3, "products": {"A": 180, "B": 200}},
        {"id": "OT3", "due": 20, "cluster": 2, "products": {"C": 400}},
        {"id": "OT4", "due": 20, "cluster": 4, "products": {"A": 150, "C": 200}},
        # Día 2-3 - OTs intermedias (completadas en ~36h)
        {"id": "OT5", "due": 40, "cluster": 1, "products": {"A": 500, "B": 300}},
        {"id": "OT6", "due": 60, "cluster": 2, "products": {"C": 350, "B": 200}},
        {"id": "OT7", "due": 60, "cluster": 5, "products": {"B": 400}},
        {"id": "OT8", "due": 60, "cluster": 3, "products": {"A": 250, "B": 150, "C": 100}},
        {"id": "OT9", "due": 60, "cluster": 4, "products": {"C": 450}},
        # Día 4-5 - OTs con más tiempo (completadas en ~55h)
        {"id": "OT10", "due": 80, "cluster": 2, "products": {"B": 300, "A": 200}},
        {"id": "OT11", "due": 80, "cluster": 5, "products": {"A": 600, "B": 400}},
        {"id": "OT12", "due": 80, "cluster": 3, "products": {"C": 250, "A": 150}},
        {"id": "OT13", "due": 80, "cluster": 4, "products": {"A": 400, "C": 300}},
        {"id": "OT14", "due": 80, "cluster": 1, "products": {"B": 350}},
        # Día 6-7 - OTs con tiempo suficiente (completadas en ~73h)
        {"id": "OT15", "due": 100, "cluster": 5, "products": {"C": 500, "B": 200}},
        {"id": "OT16", "due": 100, "cluster": 2, "products": {"A": 400}},
        {"id": "OT17", "due": 100, "cluster": 3, "products": {"B": 250, "C": 150}},
        {"id": "OT18", "due": 100, "cluster": 4, "products": {"C": 550, "A": 300}},
        {"id": "OT19", "due": 100, "cluster": 1, "products": {"A": 350, "B": 250}},
        # Más OTs para llenar el calendario (completadas en ~73h)
        {"id": "OT20", "due": 100, "cluster": 5, "products": {"B": 450, "A": 200}},
        {"id": "OT21", "due": 100, "cluster": 2, "products": {"A": 300, "C": 250}},
        {"id": "OT22", "due": 100, "cluster": 3, "products": {"C": 500}},
        {"id": "OT23", "due": 100, "cluster": 4, "products": {"B": 380, "A": 220}},
        {"id": "OT24", "due": 100, "cluster": 1, "products": {"A": 450, "B": 300, "C": 200}},
    ],
    "machines": {
        "Linea_1": {"capacity": 120, "available_at": 0, "last_format": None},
        "Linea_2": {"capacity": 90, "available_at": 0, "last_format": None},
    },
    "setup_times": {
        "A-B": 1.5,
        "B-A": 1.5,
        "A-C": 2.0,
        "C-A": 2.0,
        "B-C": 1.0,
        "C-B": 1.0,
    },
    "horizonte_aprovechamiento": 12,
    "costo_inventario_unitario": 0.002,
    "default_setup_time": 1.5,
    "start_datetime": "2024-01-25T08:00:00",  # Jueves 25 de enero de 2024 a las 8 AM
    "work_hours_per_day": 24.0,  # Producción 24/7
    "work_start_hour": 0,  # No se usa en modo 24/7
    "work_days": [0, 1, 2, 3, 4, 5, 6]  # Todos los días (24/7)
}

# Datos de testeo formato antiguo (compatibilidad)
datos_testeo_antiguo = {
    "orders": [
        {"id": "OT1001", "due": 12, "qty": 800, "cluster": 5, "format": "A"},
        {"id": "OT1002", "due": 18, "qty": 500, "cluster": 4, "format": "B"},
        {"id": "OT1003", "due": 20, "qty": 700, "cluster": 3, "format": "A"},
        {"id": "OT1004", "due": 28, "qty": 1200, "cluster": 2, "format": "C"},
        {"id": "OT1005", "due": 30, "qty": 600, "cluster": 4, "format": "B"},
        {"id": "OT1006", "due": 40, "qty": 1500, "cluster": 1, "format": "A"},
        {"id": "OT1007", "due": 45, "qty": 900, "cluster": 2, "format": "C"},
    ],
    "machines": {
        "Linea_1": {"capacity": 120, "available_at": 0, "last_format": None},
        "Linea_2": {"capacity": 90, "available_at": 0, "last_format": None},
    },
    "setup_times": {
        "A-B": 1.5,
        "B-A": 1.5,
        "A-C": 2.0,
        "C-A": 2.0,
        "B-C": 1.0,
        "C-B": 1.0,
    },
    "horizonte_aprovechamiento": 12,
    "costo_inventario_unitario": 0.002,
    "default_setup_time": 1.5,
    "start_datetime": "2024-01-25T08:00:00",
    "work_hours_per_day": 24.0,
    "work_start_hour": 0,
    "work_days": [0, 1, 2, 3, 4, 5, 6]
}

# Usar el modelo optimizado por defecto
datos_testeo = datos_testeo_optimizado

def probar_api(usar_optimizado=True):
    """Función principal para probar la API"""
    print("=" * 60)
    print("PRUEBA DE API - PROGRAMACIÓN DE PRODUCCIÓN")
    print("=" * 60)
    
    # Seleccionar datos de testeo
    global datos_testeo
    if usar_optimizado:
        datos_testeo = datos_testeo_optimizado
        print("\n🔬 MODO: Modelo Optimizado (OTs con múltiples productos)")
        print("   Este modelo agrupa productos del mismo tipo para minimizar setups")
        print("   y respeta las fechas límite de todas las OTs\n")
    else:
        datos_testeo = datos_testeo_antiguo
        print("\n📋 MODO: Formato Antiguo (compatibilidad)")
        print("   Cada OT tiene un solo producto\n")
    
    print(f"📡 Conectando a: {API_URL}")
    print(f"⏰ Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Verificar que el servidor esté corriendo
        print("1️⃣ Verificando salud del servidor...")
        health_response = requests.get("http://localhost:8000/health", timeout=5)
        if health_response.status_code == 200:
            print("   ✅ Servidor está funcionando correctamente\n")
        else:
            print(f"   ⚠️ Servidor respondió con código: {health_response.status_code}\n")
    except requests.exceptions.ConnectionError:
        print("   ❌ ERROR: No se puede conectar al servidor")
        print("   💡 Asegúrate de que el servidor esté corriendo con: python3 app.py")
        return
    except Exception as e:
        print(f"   ⚠️ Error al verificar servidor: {e}\n")
    
    # Realizar la petición principal
    print("2️⃣ Enviando datos de testeo al endpoint /schedule...")
    print(f"   📦 Órdenes de trabajo: {len(datos_testeo['orders'])}")
    print(f"   🏭 Máquinas: {len(datos_testeo['machines'])}")
    
    try:
        response = requests.post(API_URL, json=datos_testeo, timeout=30)
        
        print(f"\n3️⃣ Respuesta recibida (Código: {response.status_code})\n")
        
        if response.status_code == 200:
            resultado = response.json()
            
            # Mostrar el schedule formateado
            print("=" * 60)
            print("PROGRAMA DE PRODUCCIÓN GENERADO")
            print("=" * 60)
            print()
            
            for task in resultado["schedule"]:
                if task["type"] == "SETUP":
                    print(f"🔧 [{task['machine']}] SETUP")
                    print(f"   ⏱️  {task['start']:.2f}h → {task['end']:.2f}h")
                    print(f"   ⏳ Duración: {task.get('duration', task['end'] - task['start']):.2f}h")
                    if task.get('format'):
                        print(f"   🏷️  Cambio a: {task['format']}")
                    if task.get('color'):
                        print(f"   🎨 Color: {task['color']}")
                    print()
                elif task["type"] == "PRODUCTION":
                    # Formato nuevo: producción optimizada
                    product = task.get('product') or task.get('format') or "Producto"
                    quantity = task.get('quantity') or task.get('qty_cliente') or 0
                    ot_ids = task.get('ot_ids') or ([task.get('id')] if task.get('id') else [])
                    
                    print(f"📦 [{task['machine']}] Producción: {product}")
                    print(f"   ⏱️  {task['start']:.2f}h → {task['end']:.2f}h")
                    print(f"   📊 Cantidad: {quantity} unidades")
                    if ot_ids:
                        print(f"   📋 OTs beneficiadas: {', '.join(ot_ids)}")
                    on_time = task.get('on_time', True)
                    print(f"   {'✅ A TIEMPO' if on_time else '⚠️ ATRASADO'}")
                    if task.get('color'):
                        print(f"   🎨 Color: {task['color']}")
                    print()
                else:
                    # Formato antiguo: compatibilidad
                    print(f"📋 [{task['machine']}] {task.get('id', 'OT')}")
                    print(f"   ⏱️  {task['start']:.2f}h → {task['end']:.2f}h")
                    on_time = task.get('on_time', task['end'] <= task['due']) if task.get('due') else True
                    if task.get('due'):
                        print(f"   📅 Due: {task['due']:.2f}h {'✅ A TIEMPO' if on_time else '⚠️ ATRASADO'}")
                    if task.get('qty_cliente'):
                        print(f"   📦 Cliente: {task['qty_cliente']} unidades")
                    if task.get('qty_extra'):
                        print(f"   ➕ Extra: {task['qty_extra']} unidades")
                    if task.get('format'):
                        print(f"   🏷️  Formato: {task['format']}")
                    if task.get('color'):
                        print(f"   🎨 Color: {task['color']}")
                    print()
            
            # Mostrar resumen
            print("=" * 60)
            print("RESUMEN ESTADÍSTICO")
            print("=" * 60)
            summary = resultado["summary"]
            print(f"📊 Total OTs procesadas: {summary['total_ots']}")
            print(f"🔧 Total Setups realizados: {summary['total_setups']}")
            print(f"⏰ Total de horas programadas: {summary['total_horas']:.2f}h")
            print(f"📦 Cantidad total para cliente: {summary['qty_total_cliente']} unidades")
            print(f"➕ Cantidad total extra: {summary['qty_total_extra']} unidades")
            
            if summary['atrasos']:
                print(f"\n⚠️ ATRASOS DETECTADOS: {len(summary['atrasos'])}")
                for atraso in summary['atrasos']:
                    print(f"   • {atraso['ot_id']}: {atraso['atraso_horas']:.2f}h de atraso (cluster {atraso['cluster']})")
            else:
                print("\n✅ Todas las OTs están a tiempo")
            
            # Mostrar información sobre schedule_by_machine
            if "schedule_by_machine" in resultado:
                print("\n" + "=" * 60)
                print("VISTA POR MÁQUINA (para visualización Gantt)")
                print("=" * 60)
                for machine, tasks in resultado["schedule_by_machine"].items():
                    print(f"\n🏭 {machine}: {len(tasks)} tareas")
                    for task in tasks:
                        if task["type"] == "SETUP":
                            task_type = "🔧 SETUP"
                            product_info = f" → {task.get('format', '')}" if task.get('format') else ""
                        elif task["type"] == "PRODUCTION":
                            product = task.get('product') or task.get('format') or "Producto"
                            task_type = f"📦 {product}"
                        else:
                            task_type = f"📋 {task.get('id', 'OT')}"
                        
                        # Mostrar fecha/hora si está disponible, sino mostrar horas
                        if task.get('start_datetime_str') and task.get('end_datetime_str'):
                            print(f"   {task_type} - {task['start_datetime_str']} → {task['end_datetime_str']} ({task.get('duration', 0):.2f}h)")
                        else:
                            print(f"   {task_type} - {task['start']:.2f}h → {task['end']:.2f}h ({task.get('duration', 0):.2f}h)")
            
            # Guardar resultado en archivo JSON
            archivo_resultado = "resultado_testeo.json"
            with open(archivo_resultado, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Resultado completo guardado en: {archivo_resultado}")
            
            print("\n" + "=" * 60)
            print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
            print("=" * 60)
            
        else:
            print(f"❌ Error en la respuesta:")
            print(f"   Código: {response.status_code}")
            print(f"   Mensaje: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ ERROR: La petición tardó demasiado (>30s)")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR en la petición: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: No se pudo parsear la respuesta JSON: {e}")
        print(f"   Respuesta recibida: {response.text[:500]}")
    except Exception as e:
        print(f"❌ ERROR inesperado: {e}")

if __name__ == "__main__":
    import sys
    
    # Por defecto usar modelo optimizado, pero permitir cambiar con argumento
    usar_optimizado = True
    if len(sys.argv) > 1:
        if sys.argv[1] == "--antiguo" or sys.argv[1] == "-a":
            usar_optimizado = False
    
    probar_api(usar_optimizado=usar_optimizado)
    
    print("\n" + "=" * 60)
    print("💡 TIP: Usa 'python3 test_api.py --antiguo' para probar el formato antiguo")
    print("=" * 60)

