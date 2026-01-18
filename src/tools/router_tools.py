import os
import logging
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .translation_tools import expand_queries_multilingual
from ..state import AgentState

logger = logging.getLogger(__name__)

def update_next_node(state: AgentState, current_step: str) -> str:
    """Determine the next node in the plan after the current step."""
    plan = state.get("research_plan", [])
    try:
        current_index = plan.index(current_step)
        if current_index + 1 < len(plan):
            return plan[current_index + 1]
    except (ValueError, IndexError):
        pass
    return "END"

def plan_research_node(state: AgentState) -> dict:
    """Analyze the topic and decide which research sources are relevant."""
    logger.info("Planning research strategy...")
    topic = state["topic"]
    
    # If a research plan is already provided (e.g., from the GUI), keep it
    # BUT if we are in a re-planning loop (iteration > 0), we want the LLM to DECIDE new sources
    if state.get("research_plan") and state.get("iteration_count", 0) == 0:
        logger.info("Using existing research plan provided in state.")
        return {
            "research_plan": state["research_plan"],
            "next_node": state.get("next_node", state["research_plan"][0]),
            "iteration_count": 0
        }
    
    persona = state.get("persona", "general")
    persona_configs = {
        "general": "un coordinador de investigación generalista, equilibrado y objetivo.",
        "business": "un analista de mercado con enfoque en ROI, tendencias comerciales y competencia.",
        "tech": "un arquitecto de software interesado en especificaciones técnicas, escalabilidad y arquitecturas.",
        "academic": "un revisor científico que busca rigor, artículos de investigación peer-reviewed y metodología.",
        "pm": "un Product Manager enfocado en necesidades del usuario, viabilidad del producto y priorización de funcionalidades."
    }
    persona_context = persona_configs.get(persona, persona_configs["general"])
    
    prompt = f"""
    Eres {persona_context} Tu tarea es analizar un tema y decidir qué fuentes de información son las más pertinentes para investigar.
    
    TEMA DE INVESTIGACIÓN: {topic}
    
    FUENTES DISPONIBLES:
    - wiki: Para contexto general, definiciones e historia.
    - web: Para noticias recientes, blogs y artículos generales.
    - arxiv: Para artículos científicos de física, matemáticas e informática.
    - scholar: Para publicaciones académicas y ciencia general.
    - github: Para código fuente, librerías y repositorios de software.
    - hn: Para discusiones técnicas y tendencias en Silicon Valley.
    - so: Para problemas técnicos específicos y soluciones de programación.
    - youtube: Para explicaciones visuales, tutoriales y comparativas.
    - reddit: Para opiniones de la comunidad, experiencias reales y discusiones informales.
    - reddit: Para opiniones de la comunidad, experiencias reales y discusiones informales.
    """
    
    # Conditionally add local_rag if files exist
    kb_path = "./knowledge_base"
    has_local_files = False
    if os.path.exists(kb_path) and any(f for f in os.listdir(kb_path) if not f.startswith('.')):
        has_local_files = True
        prompt += "\n    - local_rag: Para consultar la base de conocimientos local y archivos proporcionados por el usuario."
    
    prompt += """
    
    INSTRUCCIONES:
    1. Responde ÚNICAMENTE con una lista JSON de las fuentes que deben ser consultadas.
    2. Prioriza la calidad sobre la cantidad. No selecciones todas si no son necesarias.
    3. Si el tema es muy técnico/programación, prioriza github, so y scholar.
    4. Si el tema es una noticia o tendencia, prioriza web, hn y reddit.
    
    EJEMPLO DE SALIDA:
    ["wiki", "web", "arxiv"]
    
    LISTA DE FUENTES SELECCIONADAS:
    """
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    from ..config import settings
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0.1,
        request_timeout=settings.llm_request_timeout
    )
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "[" in content and "]" in content:
            content = content[content.find("["):content.rfind("]")+1]
        
        selected_sources = json.loads(content)
        logger.info(f"Sources selected: {selected_sources}")
        
        # Multilingual expansion
        expanded_queries = expand_queries_multilingual(topic)
        
        first_node = selected_sources[0] if selected_sources else "generate_report"
        
        return {
            "research_plan": selected_sources,
            "next_node": first_node,
            "iteration_count": state.get("iteration_count", 0),
            "queries": expanded_queries
        }
    except Exception as e:
        logger.error(f"Error in planning: {e}")
        return {
            "research_plan": ["wiki", "web"],
            "next_node": "wiki",
            "iteration_count": state.get("iteration_count", 0)
        }

def evaluate_research_node(state: AgentState) -> dict:
    """Evaluate if the gathered research is sufficient or if more is needed."""
    logger.info("Evaluating research sufficiency with LLM...")
    
    iteration = state.get("iteration_count", 0)
    topic = state["topic"]
    summary = state.get("consolidated_summary", "")
    
    # Phase 7: News Digest should be fast. Skip refinement loops for News Editor.
    if state.get("persona") == "news_editor":
        logger.info("News Editor persona detected. Skipping refinement loops for speed.")
        return {"next_node": "END", "evaluation_report": "Salto de evaluación para modo noticias."}

    # Safety: Hard limit on iterations to ensure we don't loop infinitely
    # User requested max 2 loops (Iteration 0 and Iteration 1)
    if iteration >= 1:
        logger.info("Maximum iterations (2) reached. Finalizing.")
        return {
            "next_node": "END", 
            "evaluation_report": "Límite de 2 iteraciones alcanzado.",
            "topic": state.get("original_topic", state.get("topic", ""))
        }
    
    prompt = f"""
    Eres un Crítico de Investigación y Fact-Checker experto. Tu tarea es evaluar si la siguiente síntesis es completa y, sobre todo, si las afirmaciones críticas están debidamente verificadas.

    TEMA ORIGINAL: {topic}
    SÍNTESIS ACTUAL:
    {summary}

    INSTRUCCIONES DE EVALUACIÓN (PHASE 5):
    1. Revisa la sección "## Verificación de Datos" de la síntesis (si existe).
    2. Identifica si hay afirmaciones de ALTO IMPACTO que parezcan dudosas o solo tengan una fuente informal.
    3. Responde en formato JSON:
       - "sufficient": booleano (true si es sólido, false si falta verificación).
       - "gaps": lista de temas a profundizar (opcional).
       - "fact_check_queries": lista de consultas específicas para VERIFICAR las dudas encontradas.
       - "reasoning": explicación breve.

    Si no hay dudas críticas, marca "sufficient": true.

    EJEMPLO:
    {{"sufficient": false, "gaps": [], "fact_check_queries": ["¿Es cierto que X soporta Y?"], "reasoning": "Duda sobre compatibilidad."}}
    """
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    from langchain_ollama import ChatOllama
    from ..config import settings
    llm = ChatOllama(base_url=ollama_base_url, model=ollama_model, temperature=0.1, request_timeout=settings.llm_request_timeout)
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "{" in content and "}" in content:
            content = content[content.find("{"):content.rfind("}")+1]
        
        evaluation = json.loads(content)
        sufficient = evaluation.get("sufficient", True)
        gaps = evaluation.get("gaps", [])
        fact_check_queries = evaluation.get("fact_check_queries", [])
        reasoning = evaluation.get("reasoning", "")
        
        if not sufficient and (gaps or fact_check_queries):
            logger.info(f"Fact-checking required. Queries: {fact_check_queries}")
            # Trigger RE-PLAN with gaps and queries
            combined_gap = f"VERIFICAR Y PROFUNDIZAR: {', '.join(gaps + fact_check_queries)}"
            return {
                "next_node": "plan_research", 
                "topic": combined_gap,
                "iteration_count": iteration + 1,
                "evaluation_report": reasoning
            }
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
    
    return {
        "next_node": "END", 
        "topic": state.get("original_topic", state.get("topic", "")), # Reset to original if sufficient
        "evaluation_report": "Investigación considerada suficiente o error en evaluación."
    }

def router_node(state: AgentState):
    """Router function to decide the next step in LangGraph."""
    plan = state.get("research_plan", [])
    current_node = state.get("next_node", "END")
    
    if current_node == "END":
        return "consolidate_research"
        
    mapping = {
        "wiki": "search_wiki",
        "web": "search_web",
        "arxiv": "search_arxiv",
        "scholar": "search_scholar",
        "github": "search_github",
        "hn": "search_hn",
        "so": "search_so",
        "youtube": "search_videos",
        "reddit": "search_reddit",
        "local_rag": "local_rag"
    }
    
    return mapping.get(current_node, "consolidate_research")
