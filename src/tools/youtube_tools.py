# src/tools/youtube_tools.py

from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.tools import YouTubeSearchTool

# Importamos la definición de AgentState desde el archivo agent.py
# El '..' indica que subimos un nivel en la estructura de directorios para encontrar el módulo.
from ..agent import AgentState

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
        # Esta herramienta se encarga de hacer la llamada a la API de YouTube por nosotros.
        tool = YouTubeSearchTool()

        # Ejecutamos la búsqueda. Le pedimos explícitamente los 10 resultados más relevantes.
        # La herramienta devuelve una cadena con formato de lista de Python, ej: "['/watch?v=...', '/watch?v=...']"
        search_results_str = tool.run(f"{topic}, top 10 relevant videos")

        # Convertimos la cadena de resultados en una lista real de Python.
        # Es importante usar eval() aquí, ya que la salida de la herramienta está diseñada para ello.
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

    # Definimos el prompt (instrucción) para nuestro resumen.
    # Queremos un resumen técnico y conciso.
    summary_prompt = """
    Escribe un resumen ejecutivo conciso de la siguiente transcripción de vídeo.
    El resumen debe estar dirigido a una audiencia técnica, destacando los puntos clave,
    conceptos principales y conclusiones importantes.

    Transcripción:
    "{text}"

    RESUMEN EJECUTIVO CONCISO:
    """

    # Cargamos una "cadena de resumen" de LangChain.
    # 'map_reduce' es eficiente para documentos largos como las transcripciones.
    summarize_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=summary_prompt,
        combine_prompt=summary_prompt
    )

    for i, url_suffix in enumerate(video_urls):
        full_url = f"https://www.youtube.com{url_suffix}"
        print(f"\nProcesando vídeo {i+1}/{len(video_urls)}: {full_url}")

        try:
            # Usamos el cargador de YouTube de LangChain.
            # 'add_video_info=True' nos da acceso a metadatos como el título y el autor.
            loader = YoutubeLoader.from_youtube_url(full_url, add_video_info=True, language=["es", "en"])
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