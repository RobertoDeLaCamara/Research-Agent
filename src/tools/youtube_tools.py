# src/tools/youtube_tools.py

from langchain_ollama import ChatOllama
import os
from youtube_search import YoutubeSearch
from langchain_classic.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader

from typing import TypedDict, List
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from state import AgentState

# --------------------------------------------------------------------------
# NODO 1: BÚSQUEDA DE VÍDEOS EN YOUTUBE
# --------------------------------------------------------------------------
def search_videos_node(state: AgentState) -> dict:
    """
    Busca vídeos en YouTube y extrae sus metadatos (título, autor, URL).
    """
    print("\n--- 🔎 NODO: BUSCANDO VÍDEOS ---")
    queries = state.get("queries", {})
    search_topic = queries.get("es", state["topic"])
    print(f"Tema de búsqueda: {search_topic}")

    try:
        from utils import get_max_results
        max_results = get_max_results(state)
        import threading
        results = []
        def run_search():
            nonlocal results
            try:
                results = YoutubeSearch(search_topic, max_results=max_results).to_dict()
            except Exception as e_inner:
                print(f"❌ YouTubeSearch internal error: {e_inner}")

        thread = threading.Thread(target=run_search)
        thread.start()
        thread.join(timeout=15) # 15 seconds for search
        if thread.is_alive():
            print("⚠️ YouTube search timed out.")
            return {"video_urls": [], "video_metadata": []}

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
        from tools.router_tools import update_next_node
        return {"summaries": [], "next_node": update_next_node(state, "youtube")}

    from utils import bypass_proxy_for_ollama
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
        print(f"\nProcesando vídeo {i+1}/{len(video_urls)}: {url}")
        metadata = video_metadata[i]
        print(f"  - Título: {metadata['title']}")

        try:
            import threading
            docs = []
            def load_transcript():
                nonlocal docs
                try:
                    loader = YoutubeLoader.from_youtube_url(url, add_video_info=False, language=["es", "en"])
                    docs = loader.load()
                except Exception as e_load:
                    print(f"  - ⚠️ Loader error: {e_load}")

            thread = threading.Thread(target=load_transcript)
            thread.start()
            thread.join(timeout=20) # 20 seconds for transcript loading
            
            if thread.is_alive() or not docs:
                if thread.is_alive():
                    print("  - ⚠️ Transcript loading timed out.")
                raise ValueError("No se pudo obtener la transcripción.")

            summary = ""
            def run_summarize():
                nonlocal summary
                try:
                    summary = summarize_chain.run(docs)
                except Exception as e_sum:
                    print(f"  - ⚠️ Summarization error: {e_sum}")

            thread_sum = threading.Thread(target=run_summarize)
            thread_sum.start()
            thread_sum.join(timeout=90) # 90 seconds per video (Ollama can be slow)
            
            if thread_sum.is_alive() or not summary:
                if thread_sum.is_alive():
                    print("  - ⚠️ Video summarization timed out.")
                raise ValueError("Resumen fallido o lento.")

            summaries.append(summary.strip())
            print("  - ✅ Resumen generado desde transcripción.")

        except Exception as e:
            print(f"  - ⚠️ Error al procesar vídeo: {e}")
            print(f"  - 🔄 Usando metadatos como fallback...")
            
            try:
                # Use a more forceful prompt with XML tags and SystemMessage
                system_rules = "Eres un asistente de investigación experto. Tu tarea es generar UN solo párrafo conciso. REGLA ESTRICTA: NO incluyas preámbulos, razonamientos ni introducciones. SOLO entrega el párrafo final envuelto en etiquetas <summary> y </summary>."
                human_prompt = f"Genera un breve párrafo explicando de qué trata este vídeo basándote solo en su título: '{metadata.get('title')}'. Menciona que es una fuente audiovisual relevante para el tema {state.get('original_topic', state.get('topic', ''))}."
                
                import threading
                raw_fallback = ""
                def run_fallback():
                    nonlocal raw_fallback
                    try:
                        from langchain_core.messages import SystemMessage, HumanMessage
                        response = llm.invoke([
                            SystemMessage(content=system_rules),
                            HumanMessage(content=human_prompt)
                        ])
                        raw_fallback = response.content.strip()
                    except Exception:
                        pass
                
                thread_fb = threading.Thread(target=run_fallback)
                thread_fb.start()
                thread_fb.join(timeout=30)
                
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
                print("  - ✅ Resumen generado desde metadatos (Blindado).")
            except Exception as e_inner:
                print(f"  - ❌ Error final en fallback: {e_inner}")
                summaries.append(f"Vídeo titulado '{metadata.get('title')}' por {metadata.get('author')}. No fue posible extraer el contenido detallado debido a restricciones de YouTube.")

    from tools.router_tools import update_next_node
    return {"summaries": summaries, "next_node": update_next_node(state, "youtube")}