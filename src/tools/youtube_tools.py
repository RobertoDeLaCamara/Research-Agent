# src/tools/youtube_tools.py

from langchain_ollama import ChatOllama
import os
from youtube_search import YoutubeSearch
from langchain_classic.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader

# Importamos la definición de AgentState desde el archivo agent.py
# El '..' indica que subimos un nivel en la estructura de directorios para encontrar el módulo.
from typing import TypedDict, List
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    topic: str
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]
    web_research: List[dict]
    wiki_research: List[dict]
    arxiv_research: List[dict]
    consolidated_summary: str
    report: str
    messages: List[BaseMessage]

# --------------------------------------------------------------------------
# NODO 1: BÚSQUEDA DE VÍDEOS EN YOUTUBE
# --------------------------------------------------------------------------
def search_videos_node(state: AgentState) -> dict:
    """
    Busca vídeos en YouTube y extrae sus metadatos (título, autor, URL).

    Args:
        state (AgentState): El estado actual del agente.

    Returns:
        dict: Un diccionario con 'video_urls' y 'video_metadata' inicializado.
    """
    print("\n--- 🔎 NODO: BUSCANDO VÍDEOS ---")
    topic = state["topic"]
    print(f"Tema de búsqueda: {topic}")

    try:
        # Usamos YoutubeSearch para obtener más resultados y metadatos básicos
        max_results = 5
        results = YoutubeSearch(topic, max_results=max_results).to_dict()
        
        video_urls = []
        video_metadata = []

        for res in results:
            video_id = res['id']
            url = f"https://www.youtube.com/watch?v={video_id}"
            video_urls.append(url)
            
            # Guardamos los metadatos que ya tenemos
            video_metadata.append({
                "title": res.get('title', 'Título no disponible'),
                "author": res.get('channel', 'Autor no disponible'),
                "url": url
            })

        print(f"✅ Se encontraron {len(video_urls)} vídeos con sus metadatos.")
        return {"video_urls": video_urls, "video_metadata": video_metadata}

    except Exception as e:
        print(f"❌ Error durante la búsqueda de vídeos: {e}")
        return {"video_urls": [], "video_metadata": []}


# --------------------------------------------------------------------------
# NODO 2: EXTRACCIÓN Y RESUMEN DE TRANSCRIPCIONES
# --------------------------------------------------------------------------
def summarize_videos_node(state: AgentState) -> dict:
    """
    Genera resúmenes para los vídeos usando las transcripciones.
    """
    print("\n--- 📝 NODO: EXTRAYENDO Y RESUMIENDO VÍDEOS ---")
    video_urls = state["video_urls"]
    video_metadata = state["video_metadata"]
    summaries = []

    if not video_urls:
        print("⚠️ No se encontraron vídeos para resumir. Saltando este paso.")
        return {"summaries": []}

    # Aseguramos que las peticiones locales no pasen por un proxy.
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
    os.environ["no_proxy"] = "localhost,127.0.0.1"

    # Inicializamos el modelo de lenguaje local vía Ollama.
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0
    )

    summarize_chain = load_summarize_chain(llm, chain_type="map_reduce")

    for i, url in enumerate(video_urls):
        print(f"\nProcesando vídeo {i+1}/{len(video_urls)}: {url}")
        metadata = video_metadata[i]
        print(f"  - Título: {metadata['title']}")

        try:
            # Cargamos la transcripción (intentando español e inglés)
            loader = YoutubeLoader.from_youtube_url(url, add_video_info=False, language=["es", "en"])
            docs = loader.load()

            # Resumimos
            summary = summarize_chain.run(docs)
            summaries.append(summary)
            print("  - ✅ Resumen generado.")

        except Exception as e:
            print(f"  - ⚠️ Error al procesar {url}: {e}")
            summaries.append("No fue posible generar un resumen para este vídeo.")

    return {"summaries": summaries}