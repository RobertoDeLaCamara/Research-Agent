import os
import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from state import AgentState

logger = logging.getLogger(__name__)

def consolidate_research_node(state: AgentState) -> dict:
    """Synthesize all collected information into a consolidated report."""
    logger.info("Starting research synthesis...")
    
    topic = state["topic"]
    wiki = state.get("wiki_research", [])
    web = state.get("web_research", [])
    arxiv = state.get("arxiv_research", [])
    scholar = state.get("scholar_research", [])
    github = state.get("github_research", [])
    hn = state.get("hn_research", [])
    so = state.get("so_research", [])
    reddit = state.get("reddit_research", [])
    yt_summaries = state.get("summaries", [])
    
    # Build context for LLM
    context = f"RESEARCH TOPIC: {topic}\n\n"
    
    if wiki:
        context += "--- INFORMACIÓN DE WIKIPEDIA ---\n"
        for item in wiki:
            context += f"Título: {item.get('title')}\nContenido: {item.get('summary')}\n\n"
            
    if web:
        context += "--- RESULTADOS DE BÚSQUEDA WEB ---\n"
        for item in web:
            context += f"Contenido: {item.get('content', item.get('snippet', ''))}\n\n"
            
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
            
    if yt_summaries:
        context += "--- RESÚMENES DE YOUTUBE ---\n"
        for i, summary in enumerate(yt_summaries):
            context += f"Video {i+1}: {summary}\n\n"

    prompt = f"""
Eres un experto analista de investigación senior. Tu tarea es producir una SÍNTESIS EJECUTIVA CONSOLIDADA, PROFESIONAL Y PERFECTAMENTE FORMATEADA.

REGLAS DE FORMATO MANDATORIAS:
1. ESTRUCTURA HIERÁRQUICA: Divide el informe en Secciones (H2) y Subtemas (H3).
2. PROHIBIDO ENUMERAR ESTRUCTURA: NO uses números (1., 2., 3.) para los títulos de secciones ni para los subtemas.
3. INDENTACIÓN DE DETALLES: Los detalles bajo cada subtema DEBEN usar viñetas (*) y estar indentados.

EJEMPLO DE ESTRUCTURA CORRECTA (BIEN):
## Tendencias Clave
### Avances en IA Generativa
* Se ha observado un incremento en la eficiencia de los modelos...
* Los nuevos algoritmos permiten una mayor precisión en...

EJEMPLO DE ESTRUCTURA ERRÓNEA (MAL) - NO HACER ESTO:
## 1. Tendencias Clave
## 2. Avances en IA Generativa
3. Se ha observado un incremento...
4. Los nuevos algoritmos...

Instrucciones de Contenido:
- Análisis Exhaustivo: Desarrolla cada sección con profundidad técnica (Introducción, Tendencias Clave, Tecnologías Emergentes, Implementaciones de Código, Conclusiones).
- Integración Multifuente: Conecta hallazgos de todas las fuentes (GitHub, arXiv, etc.) con referencias [Nombre](URL).

FORMATO DE SALIDA: Solo Markdown puro. Sin introducciones ni comentarios adicionales.

INFORMACIÓN PARA SINTETIZAR:
{context}
    """

    # Inicialización del LLM
    from utils import bypass_proxy_for_ollama
    bypass_proxy_for_ollama()
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0.3
    )

    try:
        print("Generando síntesis consolidada...")
        response = llm.invoke([HumanMessage(content=prompt)])
        consolidated_text = response.content
        print("✅ Síntesis completada.")
        return {"consolidated_summary": consolidated_text}
    except Exception as e:
        print(f"❌ Error durante la síntesis: {e}")
        return {"consolidated_summary": "No fue posible generar la síntesis consolidada."}
