import os
import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state import AgentState

logger = logging.getLogger(__name__)

def consolidate_research_node(state: AgentState) -> dict:
    """Synthesize all collected information into a consolidated report."""
    logger.info("Starting research synthesis...")
    
    topic = state.get("original_topic", state.get("topic", ""))
    wiki = state.get("wiki_research", [])
    web = state.get("web_research", [])
    arxiv = state.get("arxiv_research", [])
    scholar = state.get("scholar_research", [])
    github = state.get("github_research", [])
    hn = state.get("hn_research", [])
    so = state.get("so_research", [])
    reddit = state.get("reddit_research", [])
    local = state.get("local_research", [])
    yt_summaries = state.get("summaries", [])
    persona = state.get("persona", "general")
    
    # Build context for LLM
    source_meta = state.get("source_metadata", {})
    context = f"RESEARCH TOPIC: {topic}\n\n"
    context += "--- METADATOS DE FIABILIDAD POR FUENTE ---\n"
    for src, meta in source_meta.items():
        context += f"Fuente: {src} | Confianza: {meta.get('reliability', 'N/A')}/5 | Tipo: {meta.get('source_type', 'N/A')}\n"
    context += "\n"
    
    if wiki:
        context += "--- INFORMACIÓN DE WIKIPEDIA ---\n"
        for item in wiki:
            context += f"Título: {item.get('title')}\nContenido: {item.get('summary')}\n\n"
            
    if web:
        context += "--- RESULTADOS DE BÚSQUEDA WEB ---\n"
        for item in web:
            context += f"Fuente: {item.get('title', 'Web Result')}\nURL: {item.get('url', 'N/A')}\nContenido: {item.get('content', item.get('snippet', ''))}\n\n"
            
    if arxiv:
        context += "--- ARTÍCULOS CIENTÍFICOS (ARXIV) ---\n"
        for item in arxiv:
            context += f"Título: {item.get('title')}\nResumen: {item.get('summary')}\nURL: {item.get('url')}\n\n"
            
    if scholar:
        context += "--- ARTÍCULOS ACADÉMICOS DESTACADOS (SEMANTIC SCHOLAR) ---\n"
        for item in scholar:
            context += f"Título: {item.get('title')} ({item.get('year', 'N/A')})\n"
            context += f"Autores: {item.get('authors')}\n"
            context += f"Resumen: {item.get('content')}\n"
            context += f"URL: {item.get('url')}\n\n"
            
    if github:
        context += "--- REPOSITORIOS Y CÓDIGO (GITHUB) ---\n"
        for item in github:
            context += f"Repo: {item.get('name')}\nDescripción: {item.get('description')}\nEstrellas: {item.get('stars')}\nURL: {item.get('url')}\n\n"
            
    if hn:
        context += "--- DISCUSIONES EN HACKER NEWS ---\n"
        for item in hn:
            context += f"Título: {item.get('title')}\nAutor: {item.get('author')}\nPuntos: {item.get('points')}\nURL: {item.get('url')}\n\n"
            
    if so:
        context += "--- PREGUNTAS TÉCNICAS (STACK OVERFLOW) ---\n"
        for item in so:
            context += f"Título: {item.get('title')}\nScore: {item.get('score')}\nResuelta: {item.get('is_answered')}\nURL: {item.get('url')}\n\n"
            
    if reddit:
        context += "--- DISCUSIONES Y OPINIONES (REDDIT) ---\n"
        for item in reddit:
            context += f"Contenido: {item.get('content', item.get('snippet', ''))}\nURL: {item.get('url')}\n\n"
            
    if local:
        context += "--- CONOCIMIENTO LOCAL (RAG) ---\n"
        for item in local:
            context += f"Fuente: {item.get('title')}\nUbicación: {item.get('url')}\nContenido: {item.get('content')}\n\n"

    if yt_summaries:
        context += "--- RESÚMENES DE YOUTUBE ---\n"
        video_meta = state.get("video_metadata", [])
        for i, summary in enumerate(yt_summaries):
            title = "Video desconocido"
            url = "URL desconocida"
            if i < len(video_meta):
                title = video_meta[i].get("title", title)
                url = video_meta[i].get("url", url)
            
            context += f"Fuente: {title}\nURL: {url}\nContenido: {summary}\n\n"

    # Context safety truncation for local LLMs
    from ..config import settings
    MAX_CHARS = settings.max_synthesis_context_chars
    if len(context) > MAX_CHARS:
        logger.warning(f"Context too large ({len(context)} chars). Pruning...")
        context = context[:MAX_CHARS] + "\n\n[... CONTENIDO TRUNCADO POR EXCESO DE VOLUMEN ...]"

    # Persona-based context for synthesis
    persona_configs = {
        "general": "un experto analista de investigación senior. Tu tono es profesional, equilibrado y objetivo.",
        "business": "un consultor estratégico de negocios. Tu enfoque es el ROI, la viabilidad comercial y el impacto estratégico.",
        "tech": "un arquitecto de software senior (CTO). Tu tono es altamente técnico, preciso y enfocado en la implementación.",
        "academic": "un revisor científico que busca rigor, artículos peer-reviewed y metodología clara. Prioriza arXiv y Scholar.",
        "pm": "un Product Manager enfocado en necesidades del usuario, viabilidad y priorización de funciones.",
        "news_editor": "un Editor de Noticias de última hora. Tu objetivo es la inmediatez, el impacto y la claridad. Estructura el informe como un 'Daily Digest' con Titulares, Resumen Ejecutivo (TL;DR) y contexto de las últimas 24-48 horas."
    }
    persona_context = persona_configs.get(persona, persona_configs["general"])

    system_rules = f"""
Eres {persona_context} Tu tarea es producir una SINTESIS EJECUTIVA CONSOLIDADA, PROFESIONAL Y CRÍTICA.

REGLAS DE FORMATO MANDATORIAS:
1. ESTRUCTURA HIERÁRQUICA: Divide el informe en Secciones (H2) y Subtemas (H3).
2. PROHIBIDO ENUMERAR ESTRUCTURA: NO uses números (1., 2., 3.) para los títulos de secciones ni para los subtemas.
3. INDENTACIÓN DE DETALLES: Los detalles bajo cada subtema DEBEN usar viñetas (*) y estar indentados.

REGLAS DE SEGURIDAD Y LIMPIEZA (CRÍTICO):
1. **SOLO EL RESULTADO FINAL**: NO incluyas razonamientos, introducciones ("Okay", "Entiendo"), ni saludos.
2. **SIN PENSAMIENTOS**: Si tu sistema de razonamiento genera pasos intermedios, ELIMÍNALOS. Solo entrega el Markdown final.
3. **ETIQUETAS REQUERIDAS**: Debes envolver el informe final EXACTAMENTE entre las etiquetas `<report>` y `</report>`. Todo lo que esté fuera de estas etiquetas será ignorado.

INSTRUCCIONES DE ANÁLISIS ESPECIALISTA (PHASE 6 & 7):
3. PESO DE AUTORIDAD: Prioriza la información oficial de fuentes académicas y, MUY ESPECIALMENTE, del **CONOCIMIENTO LOCAL (RAG)** proporcionado por el usuario.
4. CITAS OBLIGATORIAS Y LITERALES (CRÍTICO):
   - Todas las afirmaciones deben tener una cita usando Markdown link: `[Título Corto](URL)`.
   - **LA URL DEBE SER COPIADA EXACTAMENTE** del campo `URL:` proporcionado en el contexto. 
   - SI UNA FUENTE NO TIENE URL EN EL CONTEXTO, NO INVENTES UNA. Usa el nombre de la fuente sin enlace o pon `(Fuente sin enlace)`.
   - **PROHIBIDO** usar enlaces de ejemplo como `example.com` o `youtube.com/watch?v=example1`. ESTO SE CONSIDERA UNA ALUCINACIÓN GRAVE.
   - Para archivos locales: `[mi_archivo.pdf](file://...)`.

5. IDENTIFICACIÓN DE AFIRMACIONES CLAVE: Al final del informe, añade una sección "## Verificación de Datos" con una lista de las 3 afirmaciones más críticas.

FORMATO DE SALIDA: Solo Markdown puro envuelto en etiquetas `<report>`.
"""

    human_query = f"INFORMACIÓN PARA SINTETIZAR:\n{context}"

    # Inicialización del LLM
    from ..utils import bypass_proxy_for_ollama
    bypass_proxy_for_ollama()
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0.3,
        request_timeout=240 # 4 minutes timeout for synthesis
    )

    try:
        print("Generando síntesis consolidada...")
        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=system_rules),
            HumanMessage(content=human_query)
        ])
        raw_text = response.content.strip()
        
        import re
        
        # 1. ELIMINACIÓN DE BLOQUES <think> (DeepSeek/Qwen Reasoning)
        processed_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
        
        # 2. EXTRACCIÓN POR ETIQUETAS <report>
        match = re.search(r'<report>(.*?)</report>', processed_text, re.DOTALL)
        if match:
            consolidated_text = match.group(1).strip()
        elif "<report>" in processed_text:
            consolidated_text = processed_text.split("<report>")[1].strip()
        else:
            # 3. FALLBACK: BÚSQUEDA POR ANCLAS ESTRUCTURALES
            # Buscamos encabezados Markdown o palabras clave comunes de inicio de informe
            anchors = [r'##\s+', r'Resumen:', r'SÍNTESIS:', r'Sintesis:', r'Informe:', r'Resumen ejecutivo:']
            earliest_pos = len(processed_text)
            found_anchor = False
            
            for anchor in anchors:
                a_match = re.search(anchor, processed_text, re.IGNORECASE)
                if a_match and a_match.start() < earliest_pos:
                    earliest_pos = a_match.start()
                    found_anchor = True
            
            if found_anchor:
                consolidated_text = processed_text[earliest_pos:].strip()
            else:
                # 4. LIMPIEZA HEURÍSTICA DE PREÁMBULOS (Último recurso)
                # Si no hay anclas, eliminamos líneas que parezcan razonamiento
                reasoning_patterns = [
                    r'^okay,?\s.*', r'^entendido,?\s.*', r'^analizando,?\s.*', 
                    r'^aquí tienes,?\s.*', r'^primero,?\s.*', r'^según el texto,?\s.*',
                    r'^voy a,?\s.*', r'^veamos,?\s.*', r'^the user provided,?\s.*'
                ]
                lines = processed_text.split('\n')
                start_idx = 0
                for i, line in enumerate(lines[:10]): # Solo miramos las primeras 10 líneas
                    if any(re.match(p, line.strip().lower()) for p in reasoning_patterns) or len(line.strip()) < 5:
                        start_idx = i + 1
                    else:
                        break # Encontramos la primera línea que NO parece ruido
                
                consolidated_text = "\n".join(lines[start_idx:]).strip()

        print("✅ Síntesis completada (Nuclear Cleaning).")
        
        return {"consolidated_summary": consolidated_text}
    except Exception as e:
        print(f"❌ Error durante la síntesis: {e}")
        return {"consolidated_summary": "No fue posible generar la síntesis consolidada."}
