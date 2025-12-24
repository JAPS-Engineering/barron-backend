"""
Script para probar la API de programación de producción con datos de testeo
"""
import requests
import json
from datetime import datetime

# URL de la API
API_URL = "http://localhost:8000/schedule"

# Datos de testeo (mismo formato que el archivo original)
datos_testeo = {
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
    "default_setup_time": 1.5
}

def probar_api():
    """Función principal para probar la API"""
    print("=" * 60)
    print("PRUEBA DE API - PROGRAMACIÓN DE PRODUCCIÓN")
    print("=" * 60)
    print(f"\n📡 Conectando a: {API_URL}")
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
                    if task.get('color'):
                        print(f"   🎨 Color: {task['color']}")
                    print()
                else:
                    print(f"📋 [{task['machine']}] {task['id']}")
                    print(f"   ⏱️  {task['start']:.2f}h → {task['end']:.2f}h")
                    # Usar on_time si está disponible, sino calcularlo
                    on_time = task.get('on_time', task['end'] <= task['due']) if task.get('due') else True
                    print(f"   📅 Due: {task['due']:.2f}h {'✅ A TIEMPO' if on_time else '⚠️ ATRASADO'}")
                    print(f"   📦 Cliente: {task['qty_cliente']} unidades")
                    print(f"   ➕ Extra: {task['qty_extra']} unidades")
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
                        task_type = "🔧 SETUP" if task["type"] == "SETUP" else f"📋 {task.get('id', 'OT')}"
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
    probar_api()

