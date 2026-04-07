# src/tools/youtube_tools.py

import logging
from langchain_ollama import ChatOllama
import os
from youtube_search import YoutubeSearch
from langchain_classic.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader

from ..state import AgentState
from ..llm import get_llm

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

    llm = get_llm(temperature=0)

    summarize_chain = load_summarize_chain(llm, chain_type="map_reduce")

    for i, url in enumerate(video_urls):
        logger.info(f"processing_video index={i+1} total={len(video_urls)} url={url}")
        metadata = video_metadata[i]
        logger.info(f"video_title title={metadata['title']}")

        try:
            import threading
            docs = []
            docs_container = {"data": []}
            def load_transcript():
                try:
                    loader = YoutubeLoader.from_youtube_url(url, add_video_info=False, language=["es", "en"])
                    docs_container["data"] = loader.load()
                except Exception as e_load:
                    # Detect if we are blocked by YouTube
                    if "RequestBlocked" in str(e_load) or "Could not retrieve a transcript" in str(e_load):
                        logger.warning(f"YouTube transcript blocked for {url}. Switching to fast fallback.")
                    else:
                        logger.warning("transcript_loader_error", exc_info=e_load)

            thread = threading.Thread(target=load_transcript)
            thread.start()
            thread.join(timeout=10) # Reduced timeout for faster failure

            if not thread.is_alive():
                docs = docs_container["data"]
            
            if not docs:
                if thread.is_alive():
                    logger.warning("transcript_loading_timeout")
                # Instead of raising ValueError, we directly trigger the metadata fallback
                raise StopIteration("use_metadata_fallback")

            summary = ""
            summary_container = {"data": ""}
            def run_summarize():
                try:
                    summary_container["data"] = summarize_chain.run(docs)
                except Exception as e_sum:
                    logger.warning("summarization_error", exc_info=e_sum)

            thread_sum = threading.Thread(target=run_summarize)
            thread_sum.start()
            thread_sum.join(timeout=25)

            if not thread_sum.is_alive():
                summary = summary_container["data"]
            
            if not summary:
                raise StopIteration("use_metadata_fallback")

            summaries.append(summary.strip())
            logger.info("summary_from_transcript")

        except (StopIteration, Exception) as e:
            if str(e) != "use_metadata_fallback":
                 logger.warning("video_processing_failed_using_fallback", exc_info=e)

            # --- ROBUST FALLBACK ---
            try:
                # Use metadata if transcript is blocked
                title = metadata.get('title', 'Video')
                author = metadata.get('author', 'YouTube')
                
                # Try simple LLM prompt with short timeout
                system_rules = "Genera un solo párrafo conciso (máximo 3 frases) sobre el tema."
                human_prompt = f"Resume de qué trata un vídeo titulado '{title}' para una investigación sobre '{state.get('topic')}'. Menciona que es de {author}."
                
                fallback_summary = ""
                def fast_fallback():
                    try:
                        resp = llm.invoke(human_prompt)
                        return resp.content.strip()
                    except:
                        return None

                # Non-threaded fast check
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(fast_fallback)
                    try:
                        fallback_summary = future.result(timeout=10)
                    except:
                        fallback_summary = None

                if not fallback_summary:
                    # Hardcoded zero-dependency fallback
                    fallback_summary = f"Vídeo titulado '{title}' de {author}. Contenido extraído de metadatos debido a restricciones de acceso a la transcripción en este entorno."
                
                summaries.append(fallback_summary)
                logger.info("summary_from_metadata_fallback_completed")
            except Exception as e_final:
                logger.error("extreme_fallback_failed", exc_info=e_final)
                summaries.append(f"Referencia visual: '{metadata.get('title', 'YouTube Video')}'.")

    from .router_tools import update_next_node
    return {"summaries": summaries, "next_node": update_next_node(state, "youtube")}
