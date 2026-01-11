import os
import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from state import AgentState

logger = logging.getLogger(__name__)

def chat_node(state: AgentState) -> dict:
    """Conversational node that answers user questions based on research."""
    logger.info("Processing user chat message...")
    
    topic = state.get("topic", "")
    summary = state.get("consolidated_summary", "")
    messages = state.get("messages", [])
    
    # Build context for the LLM
    context = f"TEMA DE INVESTIGACIÓN: {topic}\n\n"
    if summary:
        context += f"SÍNTESIS DE INVESTIGACIÓN:\n{summary}\n"
    else:
        context += "Aún no se ha completado la investigación detallada."
        
    system_prompt = f"""
    Eres un Asistente de Investigación experto. Tu objetivo es ayudar al usuario a entender los resultados de su investigación.
    
    CONTEXTO:
    {context}
    
    INSTRUCCIONES:
    1. Responde de forma concisa y profesional.
    2. Utiliza la información del contexto para responder.
    3. Si el usuario te pide investigar algo nuevo o profundizar en un tema relevante, incluye explícitamente la palabra "INVESTIGACIÓN:" seguida de lo que vas a buscar. 
       Ejemplo: "INVESTIGACIÓN: Profundizar en los algoritmos de consenso de Solana."
    4. El sistema detectará automáticamente si necesitas realizar más investigación basado en tu respuesta.
    5. Usa Markdown para formatear tus respuestas.
    6. REGLA ESTRICTA DE SALIDA: Responde DIRECTAMENTE al usuario. NO incluyas introducciones como "Okay", "Analizando el contexto...", ni ningún tipo de razonamiento interno antes de tu respuesta.
    """
    
    from utils import bypass_proxy_for_ollama
    bypass_proxy_for_ollama()
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    llm = ChatOllama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=0.7,
        request_timeout=90 # 90s for chat response
    )
    
    # Convert state messages to LangChain format if they aren't already
    chat_history = [SystemMessage(content=system_prompt)]
    for msg in messages:
        chat_history.append(msg)
        
    try:
        response = llm.invoke(chat_history)
        content = response.content.strip()
        
        # Blindaje: Eliminar etiquetas <think>...</think> y su contenido
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        # Eliminar etiquetas huérfanas o incompletas (defensivo)
        content = content.replace("<think>", "").replace("</think>", "").strip()

        # Actualizar el contenido del mensaje de respuesta
        response.content = content
        
        # Check if the AI itself suggests more research
        if "INVESTIGACIÓN:" in content:
            logger.info("Chat suggested more research. Updating next_node triggers.")
            
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error in chat_node: {e}")
        return {"messages": [AIMessage(content="Lo siento, ocurrió un error al procesar tu pregunta.")]}
