# src/main.py

import os
from dotenv import load_dotenv
from agent import app  # Importamos la aplicación 'app' desde nuestro archivo agent.py

def run_agent():
    """
    Función principal para configurar y ejecutar el agente de resumen de YouTube.
    """
    # Carga las variables de entorno (claves de API, configuración de correo) del archivo .env
    load_dotenv()

    # --- CONFIGURACIÓN DEL USUARIO ---
    # Aquí es donde defines el tema que quieres que el agente investigue.
    # ¡Puedes cambiar este valor por cualquier tema que te interese!
    topic_to_research = "Últimas tendencias en Inteligencia Artificial Generativa"
    # --------------------------------

    print(f"▶️  Iniciando agente para el tema: '{topic_to_research}'")

    # El estado inicial que le pasamos a nuestro agente.
    # Necesita el 'topic' para empezar y una lista vacía de 'messages'.
    initial_state = {"topic": topic_to_research, "messages": []}

    try:
        # Invocamos el agente con el estado inicial.
        # Esto iniciará el flujo de trabajo que definimos en LangGraph.
        app.invoke(initial_state)

        print("✅  El agente ha finalizado su ejecución con éxito.")

    except Exception as e:
        print(f"❌  Ha ocurrido un error durante la ejecución del agente: {e}")

# Este es el bloque estándar de Python para asegurarse de que el código
# solo se ejecute cuando el archivo es llamado directamente.
if __name__ == "__main__":
    run_agent()