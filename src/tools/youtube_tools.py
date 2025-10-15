# src/tools/youtube_tools.py

from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.tools import YouTubeSearchTool

# Importamos la definición de AgentState desde el archivo agent.py
# El '..' indica que subimos un nivel en la estructura de directorios para encontrar el módulo.
from typing import TypedDict, List
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    topic: str
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]
    report: str
    messages: List[BaseMessage]

# --------------------------------------------------------------------------
# NODO 1: BÚSQUEDA DE VÍDEOS EN YOUTUBE
# --------------------------------------------------------------------------
def search_videos_node(state: AgentState) -> dict:
    """
    Busca vídeos en YouTube basados en el tema proporcionado en el estado.

    Este nodo utiliza la herramienta 'YouTubeSearchTool' de LangChain para
    encontrar las 10 URLs de vídeo más relevantes para el tema de investigación.

    Args:
        state (AgentState): El estado actual del agente, que debe contener el 'topic'.

    Returns:
        dict: Un diccionario con la clave 'video_urls' para actualizar el estado del agente.
    """
    print("\n--- 🔎 NODO: BUSCANDO VÍDEOS ---")
    topic = state["topic"]
    print(f"Tema de búsqueda: {topic}")

    try:
        # Inicializamos la herramienta de búsqueda de YouTube.
        tool = YouTubeSearchTool()

        # Ejecutamos la búsqueda con solo el tema
        search_results_str = tool.run(topic)

        # Convertimos la cadena de resultados en una lista real de Python.
        video_urls = eval(search_results_str)

        print(f"✅ Se encontraron {len(video_urls)} vídeos.")
        return {"video_urls": video_urls}

    except Exception as e:
        print(f"❌ Error durante la búsqueda de vídeos: {e}")
        # Si hay un error, devolvemos una lista vacía para no detener el flujo.
        return {"video_urls": []}


# --------------------------------------------------------------------------
# NODO 2: EXTRACCIÓN Y RESUMEN DE TRANSCRIPCIONES
# --------------------------------------------------------------------------
def summarize_videos_node(state: AgentState) -> dict:
    """
    Para cada URL de vídeo, extrae su transcripción y genera un resumen ejecutivo.

    Este nodo itera sobre las 'video_urls' del estado. Para cada una, utiliza
    'YoutubeLoader' para obtener la transcripción y luego un LLM con una cadena
    de resumen para crear un resumen técnico.

    Args:
        state (AgentState): El estado actual del agente, que contiene 'video_urls'.

    Returns:
        dict: Un diccionario con 'summaries' y 'video_metadata' para actualizar el estado.
    """
    print("\n--- 📝 NODO: EXTRAYENDO Y RESUMIENDO VÍDEOS ---")
    video_urls = state["video_urls"]
    summaries = []
    video_metadata = []

    if not video_urls:
        print("⚠️ No se encontraron vídeos para resumir. Saltando este paso.")
        return {"summaries": [], "video_metadata": []}

    # Inicializamos el modelo de lenguaje que usaremos para resumir.
    # 'gpt-3.5-turbo-16k' es una buena opción por su gran ventana de contexto.
    llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-16k")

    # Cargamos una "cadena de resumen" de LangChain.
    # 'map_reduce' es eficiente para documentos largos como las transcripciones.
    summarize_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce"
    )

    for i, url in enumerate(video_urls):
        # Si la URL ya es completa, la usamos tal como está
        if url.startswith('https://'):
            full_url = url
        else:
            # Si es solo un sufijo, agregamos el dominio
            full_url = f"https://www.youtube.com{url}"
        
        # Limpiar caracteres HTML codificados y extraer solo el ID del video
        full_url = full_url.replace('&amp;', '&')
        
        # Extraer solo el ID del video para crear una URL limpia
        if 'watch?v=' in full_url:
            video_id = full_url.split('watch?v=')[1].split('&')[0]
            full_url = f"https://www.youtube.com/watch?v={video_id}"
        
        print(f"\nProcesando vídeo {i+1}/{len(video_urls)}: {full_url}")

        try:
            # Usamos el cargador de YouTube de LangChain.
            loader = YoutubeLoader.from_youtube_url(full_url, add_video_info=True)
            docs = loader.load()

            # Extraemos los metadatos antes de resumir
            metadata = docs[0].metadata
            title = metadata.get("title", "Título no disponible")
            author = metadata.get("author", "Autor no disponible")
            print(f"  - Título: {title}")

            # Ejecutamos la cadena de resumen sobre la transcripción.
            summary = summarize_chain.run(docs)
            summaries.append(summary)

            video_metadata.append({
                "title": title,
                "author": author,
                "url": full_url
            })
            print("  - ✅ Resumen generado.")

        except Exception as e:
            print(f"  - ⚠️ No se pudo procesar el vídeo {full_url}: {e}")
            # Si hay un error (ej. sin transcripción), añadimos un marcador
            # para que el informe final refleje que este vídeo no se pudo procesar.
            summaries.append("No fue posible generar un resumen para este vídeo (puede que no tenga transcripción).")
            video_metadata.append({
                "title": f"Vídeo no procesado en {full_url}",
                "author": "Desconocido",
                "url": full_url
            })

    return {"summaries": summaries, "video_metadata": video_metadata}