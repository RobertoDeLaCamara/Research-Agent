# src/agent.py

from typing import TypedDict, List
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END

# --- Importación de las herramientas (nodos) ---
# Importamos las funciones que realizarán el trabajo real desde nuestros archivos de herramientas.
# La sintaxis con '.' (ej. '.tools') indica una importación relativa dentro del paquete 'src'.
from .tools.youtube_tools import search_videos_node, summarize_videos_node
from .tools.reporting_tools import generate_report_node, send_email_node

# --------------------------------------------------------------------------
# 1. DEFINICIÓN DEL ESTADO DEL AGENTE (AGENT STATE)
# --------------------------------------------------------------------------
# El 'AgentState' es como la memoria a corto plazo de nuestro agente.
# Es un diccionario que se va llenando de información a medida que el agente
# completa cada paso del flujo de trabajo. LangGraph se encarga de pasar
# este estado de un nodo al siguiente.

class AgentState(TypedDict):
    """
    Define la estructura de datos que se comparte a través del grafo del agente.
    
    Atributos:
        topic (str): El tema de investigación inicial proporcionado por el usuario.
        video_urls (List[str]): Lista de URLs de videos encontrados en la búsqueda.
        video_metadata (List[dict]): Lista de diccionarios con metadatos de cada vídeo.
        summaries (List[str]): Lista de resúmenes generados para cada vídeo.
        report (str): El informe final en formato HTML.
        messages (List[BaseMessage]): Un historial de mensajes (útil para agentes más complejos).
    """
    topic: str
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]
    report: str
    messages: List[BaseMessage]

# --------------------------------------------------------------------------
# 2. CONSTRUCCIÓN DEL GRAFO DE FLUJO DE TRABAJO
# --------------------------------------------------------------------------
# Aquí es donde usamos LangGraph para definir el flujo de operaciones.
# Pensamos en ello como un diagrama de flujo, pero en código.

# Creamos una instancia del grafo, especificando que usará la estructura de 'AgentState'.
workflow = StateGraph(AgentState)

# --- Añadir los Nodos ---
# Cada nodo es un paso en nuestro proceso. Asociamos un nombre (string) a cada
# una de las funciones que importamos de nuestros archivos de herramientas.
print("Definiendo los nodos del grafo...")
workflow.add_node("search_videos", search_videos_node)
workflow.add_node("summarize_videos", summarize_videos_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("send_email", send_email_node)
print("Nodos definidos.")

# --- Añadir las Aristas (Edges) ---
# Las aristas conectan los nodos y definen el orden de ejecución.
# Nuestro flujo es lineal: un paso sigue al otro.
print("Conectando los nodos con las aristas...")
workflow.set_entry_point("search_videos") # El primer nodo en ejecutarse.
workflow.add_edge("search_videos", "summarize_videos")
workflow.add_edge("summarize_videos", "generate_report")
workflow.add_edge("generate_report", "send_email")
workflow.add_edge("send_email", END) # 'END' es un nodo especial que finaliza la ejecución.
print("Aristas conectadas.")

# --------------------------------------------------------------------------
# 3. COMPILACIÓN DEL AGENTE
# --------------------------------------------------------------------------
# El paso final es compilar la definición del flujo de trabajo en un objeto
# ejecutable. Este objeto 'app' es el que importaremos y usaremos en nuestro
# archivo principal (main.py).

print("Compilando el agente...")
app = workflow.compile()
print("¡Agente compilado y listo para usar!")

# Al ejecutar 'python src/main.py', este archivo será importado,
# y la variable 'app' estará disponible para ser invocada.