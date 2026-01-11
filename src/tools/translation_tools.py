import logging
import os
import re
from typing import List, Dict
from langchain_core.messages import HumanMessage
from utils import bypass_proxy_for_ollama

logger = logging.getLogger(__name__)

def expand_queries_multilingual(topic: str, target_languages: List[str] = ["en", "es"]) -> Dict[str, str]:
    """
    Expand a research topic into multiple languages for broader coverage.
    Returns a mapping of language code to query.
    """
    logger.info(f"Expanding queries for topic: {topic} into {target_languages}")
    
    # Mapping of ISO codes to names for the LLM
    lang_names = {
        "en": "English",
        "es": "Spanish",
        "zh": "Mandarin Chinese",
        "de": "German",
        "fr": "French",
        "ja": "Japanese"
    }
    
    target_lang_names = [lang_names.get(l, l) for l in target_languages]
    
    prompt = f"""
    Eres un experto en investigación multilingüe. Tu objetivo es traducir y optimizar el siguiente tema 
    de investigación para obtener los mejores resultados en diferentes idiomas.

    TEMA ORIGINAL: {topic}
    IDIOMAS OBJETIVO: {', '.join(target_lang_names)}

    Para cada idioma, proporciona la mejor consulta de búsqueda técnica o académica.
    Responde ÚNICAMENTE en formato JSON plano, donde las llaves son los códigos de idioma ({', '.join(target_languages)}) 
    y los valores son las consultas traducidas.

    EJEMPLO:
    {{
        "en": "Quantum computing consensus algorithms",
        "es": "Algoritmos de consenso en computación cuántica"
    }}
    """
    
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    
    from langchain_ollama import ChatOllama
    bypass_proxy_for_ollama()
    llm = ChatOllama(base_url=ollama_base_url, model=ollama_model, temperature=0.1, request_timeout=45)
    
    expanded = {lang: topic for lang in target_languages} # Fallback to original
    
    try:
        import json
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if "{" in content and "}" in content:
            content = content[content.find("{"):content.rfind("}")+1]
        
        results = json.loads(content)
        for lang in target_languages:
            if lang in results:
                expanded[lang] = results[lang]
                
    except Exception as e:
        logger.error(f"Multilingual expansion failed: {e}")
        
    return expanded

def unified_translation_to_base(text: str, target_lang: str = "es") -> str:
    """Translate results back to the base language (default: Spanish)."""
    # ... logic similar to expand_queries but for back-translation if needed ...
    pass
