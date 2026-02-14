# src/tools/youtube_tools.py

import logging
from langchain_ollama import ChatOllama
import os
from youtube_search import YoutubeSearch
from langchain_classic.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader

from typing import TypedDict, List
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from ..state import AgentState

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# NODO 1: BÚSQUEDA DE VÍDEOS EN YOUTUBE
# --------------------------------------------------------------------------
def search_videos_node(state: AgentState) -> dict:
    """
    Busca vídeos en YouTube y extrae sus metadatos (título, autor, URL).
    """
    logger.info("Searching YouTube videos...")
    queries = state.get("queries", {})
    search_topic = queries.get("es", state["topic"])
    logger.debug(f"Search topic: {search_topic}")

    try:
        from ..utils import get_max_results
        max_results = get_max_results(state)
        import threading
        results = []
        container = {"data": []}
        def run_search():
            try:
                container["data"] = YoutubeSearch(search_topic, max_results=max_results).to_dict()
            except Exception as e_inner:
                logger.error(f"YouTubeSearch error: {e_inner}")

        thread = threading.Thread(target=run_search)
        thread.start()
        thread.join(timeout=15) # 15 seconds for search
        if thread.is_alive():
            logger.warning("YouTube search timed out.")
            return {"video_urls": [], "video_metadata": []}
        results = container["data"]

        video_urls = []
        video_metadata = []

        for res in results:
            video_id = res['id']
            url = f"https://www.youtube.com/watch?v={video_id}"
            video_urls.append(url)
            
            video_metadata.append({
                "title": res.get('title', 'Título no disponible'),
                "author": res.get('channel', 'Autor no disponible'),
                "url": url
            })

        logger.info(f"Found {len(video_urls)} videos with metadata.")
        return {"video_urls": video_urls, "video_metadata": video_metadata}

    except Exception as e:
        logger.error("video_search_failed", exc_info=e)
        return {"video_urls": [], "video_metadata": []}


# --------------------------------------------------------------------------
# NODO 2: EXTRACCIÓN Y RESUMEN DE TRANSCRIPCIONES
# --------------------------------------------------------------------------
def summarize_videos_node(state: AgentState) -> dict:
    """
    Genera resúmenes para los vídeos usando las transcripciones.
    """
    logger.info("Extracting and summarizing videos...")
    video_urls = state["video_urls"]
    video_metadata = state["video_metadata"]
    summaries = []

    if not video_urls:
        logger.warning("No videos found to summarize. Skipping.")
        from .router_tools import update_next_node
        return {"summaries": [], "next_node": update_next_node(state, "youtube")}

    from ..utils import bypass_proxy_for_ollama
    bypass_proxy_for_ollama()

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0
    )

    summarize_chain = load_summarize_chain(llm, chain_type="map_reduce")

    for i, url in enumerate(video_urls):
        logger.info("processing_video", index=i+1, total=len(video_urls), url=url)
        metadata = video_metadata[i]
        logger.info("video_title", title=metadata['title'])

        try:
            import threading
            docs = []
            docs_container = {"data": []}
            def load_transcript():
                try:
                    loader = YoutubeLoader.from_youtube_url(url, add_video_info=False, language=["es", "en"])
                    docs_container["data"] = loader.load()
                except Exception as e_load:
                    logger.warning("transcript_loader_error", exc_info=e_load)

            thread = threading.Thread(target=load_transcript)
            thread.start()
            thread.join(timeout=20) # 20 seconds for transcript loading

            if not thread.is_alive():
                docs = docs_container["data"]
            if thread.is_alive() or not docs:
                if thread.is_alive():
                    logger.warning("transcript_loading_timeout")
                raise ValueError("No se pudo obtener la transcripción.")

            summary = ""
            summary_container = {"data": ""}
            def run_summarize():
                try:
                    summary_container["data"] = summarize_chain.run(docs)
                except Exception as e_sum:
                    logger.warning("summarization_error", exc_info=e_sum)

            thread_sum = threading.Thread(target=run_summarize)
            thread_sum.start()
            thread_sum.join(timeout=90) # 90 seconds per video (Ollama can be slow)

            if not thread_sum.is_alive():
                summary = summary_container["data"]
            if thread_sum.is_alive() or not summary:
                if thread_sum.is_alive():
                    logger.warning("summarization_timeout")
                raise ValueError("Resumen fallido o lento.")

            summaries.append(summary.strip())
            logger.info("summary_from_transcript")

        except Exception as e:
            logger.warning("video_processing_failed_using_fallback", exc_info=e)
            
            try:
                # Use a more forceful prompt with XML tags and SystemMessage
                system_rules = "Eres un asistente de investigación experto. Tu tarea es generar UN solo párrafo conciso. REGLA ESTRICTA: NO incluyas preámbulos, razonamientos ni introducciones. SOLO entrega el párrafo final envuelto en etiquetas <summary> y </summary>."
                human_prompt = f"Genera un breve párrafo explicando de qué trata este vídeo basándote solo en su título: '{metadata.get('title')}'. Menciona que es una fuente audiovisual relevante para el tema {state.get('original_topic', state.get('topic', ''))}."
                
                import threading
                raw_fallback = ""
                fallback_container = {"data": ""}
                def run_fallback():
                    try:
                        from langchain_core.messages import SystemMessage, HumanMessage
                        response = llm.invoke([
                            SystemMessage(content=system_rules),
                            HumanMessage(content=human_prompt)
                        ])
                        fallback_container["data"] = response.content.strip()
                    except Exception:
                        pass

                thread_fb = threading.Thread(target=run_fallback)
                thread_fb.start()
                thread_fb.join(timeout=30)

                if not thread_fb.is_alive():
                    raw_fallback = fallback_container["data"]
                if thread_fb.is_alive() or not raw_fallback:
                    raise ValueError("Fallback timed out.")
                
                # Blinded extraction with Regex
                import re
                match = re.search(r'<summary>(.*?)</summary>', raw_fallback, re.DOTALL)
                
                if match:
                    fallback_summary = match.group(1).strip()
                elif "<summary>" in raw_fallback:
                    fallback_summary = raw_fallback.split("<summary>")[1].strip()
                else:
                    # Defensive cleaning for Qwen 3 if tags are missing
                    reasoning_prefixes = ["okay", "entendido", "primero", "voy a", "analizando", "basado en el"]
                    lines = raw_fallback.split('\n')
                    if lines and any(lines[0].lower().startswith(p) for p in reasoning_prefixes):
                        fallback_summary = "\n".join(lines[1:]).strip()
                    else:
                        fallback_summary = raw_fallback
                    
                summaries.append(fallback_summary)
                logger.info("summary_from_metadata_fallback")
            except Exception as e_inner:
                logger.error("fallback_summary_failed", exc_info=e_inner)
                summaries.append(f"Vídeo titulado '{metadata.get('title')}' por {metadata.get('author')}. No fue posible extraer el contenido detallado debido a restricciones de YouTube.")

    from .router_tools import update_next_node
    return {"summaries": summaries, "next_node": update_next_node(state, "youtube")}