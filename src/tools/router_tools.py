import os
import logging
import json
from langchain_core.messages import HumanMessage
from ..llm import get_llm
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
    """
    
    # Conditionally add local_rag only if the user opted in AND files exist
    kb_path = "./knowledge_base"
    has_local_files = False
    if state.get("use_rag", False):
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
    
    llm = get_llm(temperature=0.1)
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "[" in content and "]" in content:
            content = content[content.find("["):content.rfind("]")+1]

        selected_sources = json.loads(content)

        # Belt-and-suspenders: strip local_rag if the user did not opt in,
        # regardless of what the LLM returned.
        if not state.get("use_rag", False):
            before = len(selected_sources)
            selected_sources = [s for s in selected_sources if s != "local_rag"]
            if len(selected_sources) != before:
                logger.warning("Filtered local_rag from plan: user did not enable RAG")

        logger.info(f"Sources selected: {selected_sources}")

        # Multilingual expansion
        expanded_queries = expand_queries_multilingual(topic)

        return {
            "research_plan": selected_sources,
            "next_node": "parallel_search",
            "iteration_count": state.get("iteration_count", 0),
            "queries": expanded_queries
        }
    except Exception as e:
        logger.error(f"Error in planning: {e}")
        return {
            "research_plan": ["wiki", "web"],
            "next_node": "parallel_search",
            "iteration_count": state.get("iteration_count", 0)
        }


def evaluate_research_node(state: AgentState) -> dict:
    """Evaluate the gathered research for factual accuracy.

    This node runs a fact-check pass on the consolidated synthesis.  It does NOT
    trigger re-plans — re-searching for verification of hallucinated claims only
    propagates garbage.  Instead, dubious claims are flagged as warnings in the
    report so the user can judge them.
    """
    logger.info("Evaluating research sufficiency with LLM...")

    topic = state["topic"]
    summary = state.get("consolidated_summary", "")
    research_depth = state.get("research_depth", "standard")

    # Skip evaluation entirely for quick depth — single pass is enough
    if research_depth == "quick":
        logger.info("Quick depth — skipping evaluation loop for speed.")
        return {"next_node": "END", "evaluation_report": "Salto de evaluación para modo quick."}

    # Phase 7: News Digest should be fast. Skip evaluation for News Editor.
    if state.get("persona") == "news_editor":
        logger.info("News Editor persona detected. Skipping evaluation for speed.")
        return {"next_node": "END", "evaluation_report": "Salto de evaluación para modo noticias."}

    prompt = f"""
    Eres un Crítico de Investigación y Fact-Checker experto. Tu tarea es evaluar si la síntesis es completa y las afirmaciones principales están verificadas con fuentes.

    TEMA ORIGINAL: {topic}
    NIVEL DE PROFUNDIDAD SOLICITADO: {research_depth}
    SÍNTESIS ACTUAL:
    {summary}

    INSTRUCCIONES DE EVALUACIÓN:
    1. Identifica si hay afirmaciones de ALTO IMPACTO que parezcan inventadas o sin fuente creíble.
    2. Una investigación puede ser ACEPTABLE incluso sin cubrir todos los subtemas posibles. No penalices por omisión de aspectos periféricos.
    3. "Falta de profundidad" NO es razón para marcar insuficiente. El nivel de detalle depende del tiempo de búsqueda.
    4. Responde en formato JSON:
       - "dubious_claims": lista de afirmaciones que parecen inventadas o sin respaldo (máximo 3, solo las más críticas).
       - "reasoning": explicación breve (máximo 2 líneas).

    EJEMPLO:
    {{"dubious_claims": [], "reasoning": "Afirmaciones respaldadas por fuentes, investigación aceptable."}}

    Si no hay afirmaciones factualmente dudosas, devuelve lista vacía.
    """

    from ..config import settings
    llm = get_llm(temperature=0.1, timeout=settings.llm_request_timeout)

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "{" in content and "}" in content:
            content = content[content.find("{"):content.rfind("}")+1]

        evaluation = json.loads(content)
        dubious_claims = evaluation.get("dubious_claims", [])
        reasoning = evaluation.get("reasoning", "")

        if dubious_claims:
            logger.info(f"Found {len(dubious_claims)} dubious claims — flagging in report (no re-plan)")
            warning = "\n\n---\n⚠️ **Advertencia del fact-checker**: las siguientes afirmaciones no pudieron ser verificadas y podrían ser inexactas:\n\n"
            for claim in dubious_claims:
                warning += f"- {claim}\n"
            warning += f"\n*Razonamiento del evaluador: {reasoning}*\n"
            return {
                "next_node": "END",
                "topic": state.get("original_topic", state.get("topic", "")),
                "evaluation_report": reasoning,
                "consolidated_summary": summary + warning,
            }
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")

    return {
        "next_node": "END",
        "topic": state.get("original_topic", state.get("topic", "")),
        "evaluation_report": "Investigación considerada suficiente o error en evaluación."
    }



