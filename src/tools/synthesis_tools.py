import os
from typing import List, TypedDict
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage

class AgentState(TypedDict):
    topic: str
    video_urls: List[str]
    video_metadata: List[dict]
    summaries: List[str]
    web_research: List[dict]
    wiki_research: List[dict]
    arxiv_research: List[dict]
    github_research: List[dict]
    scholar_research: List[dict]
    hn_research: List[dict]
    so_research: List[dict]
    consolidated_summary: str
    bibliography: List[str]
    pdf_path: str
    report: str
    messages: List[BaseMessage]

def consolidate_research_node(state: AgentState) -> dict:
    """
    Sintetiza toda la información recolectada en un informe consolidado único.
    """
    print("\n--- 🧠 NODO: SINTETIZANDO INVESTIGACIÓN ---")
    
    topic = state["topic"]
    wiki = state.get("wiki_research", [])
    web = state.get("web_research", [])
    arxiv = state.get("arxiv_research", [])
    scholar = state.get("scholar_research", [])
    github = state.get("github_research", [])
    hn = state.get("hn_research", [])
    so = state.get("so_research", [])
    yt_summaries = state.get("summaries", [])
    
    # Construcción del contexto para el LLM
    context = f"TEMA DE INVESTIGACIÓN: {topic}\n\n"
    
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
            
    if yt_summaries:
        context += "--- RESÚMENES DE YOUTUBE ---\n"
        for i, summary in enumerate(yt_summaries):
            context += f"Video {i+1}: {summary}\n\n"

    prompt = f"""
Eres un experto analista de investigación. Tu tarea es crear un INFORME CONSOLIDADO Y PROFESIONAL basado en la información proporcionada arriba.
El informe debe ser técnico, estructurado y fácil de leer.

Instrucciones:
1. Divide el informe en secciones lógicas (Introducción, Tendencias Clave, Tecnologías Emergentes, Implementaciones de Código, Conclusiones).
2. Integra la información de todas las fuentes (Wikipedia, Web, arXiv, Semantic Scholar, GitHub, Hacker News, Stack Overflow y YouTube) de manera fluida.
3. El lenguaje debe ser profesional y objetivo.
4. MANDATORIO: Cada vez que menciones un repositorio de GitHub, un artículo de arXiv, de Semantic Scholar, una discusión de Hacker News o una pregunta de Stack Overflow, DEBES incluir su URL correspondiente (ej. usando formato Markdown [Nombre](URL) o simplemente la URL entre paréntesis). No omitas ninguna URL proporcionada en el contexto.
5. IMPORTANTE: Responde ÚNICAMENTE con el cuerpo del informe en formato Markdown.

INFORMACIÓN PARA SINTETIZAR:
{context}
    """

    # Inicialización del LLM
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
