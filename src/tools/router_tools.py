import os
import logging
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from state import AgentState

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
    if state.get("research_plan"):
        logger.info("Using existing research plan provided in state.")
        return {
            "research_plan": state["research_plan"],
            "next_node": state.get("next_node", state["research_plan"][0]),
            "iteration_count": 0
        }
    
    prompt = f"""
    Eres un coordinador de investigación experto. Tu tarea es analizar un tema y decidir qué fuentes de información son las más pertinentes para investigar.
    
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
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0.1
    )
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "[" in content and "]" in content:
            content = content[content.find("["):content.rfind("]")+1]
        
        selected_sources = json.loads(content)
        logger.info(f"Sources selected: {selected_sources}")
        
        first_node = selected_sources[0] if selected_sources else "generate_report"
        
        return {
            "research_plan": selected_sources,
            "next_node": first_node,
            "iteration_count": 0
        }
    except Exception as e:
        logger.error(f"Error in planning: {e}")
        return {
            "research_plan": ["wiki", "web"],
            "next_node": "wiki",
            "iteration_count": 0
        }

def evaluate_research_node(state: AgentState) -> dict:
    """Evaluate if the gathered research is sufficient or if more is needed."""
    logger.info("Evaluating research sufficiency...")
    
    iteration = state.get("iteration_count", 0)
    topic = state["topic"]
    
    # Simple logic for now: only one reasoning loop allowed to avoid infinite loops
    if iteration >= 1:
        logger.info("Maximum iterations reached. Proceeding to final synthesis.")
        return {"next_node": "END"}
        
    # In a real scenario, we would use an LLM here to check for gaps in the consolidated_summary
    # For now, let's keep it simple to verify the flow works.
    
    return {"next_node": "END"}

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
        "reddit": "search_reddit"
    }
    
    return mapping.get(current_node, "consolidate_research")
