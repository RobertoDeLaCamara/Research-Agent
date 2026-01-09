# src/tools/research_tools.py

import os
import logging
from typing import List
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import WikipediaLoader
from langchain_community.tools.semanticscholar.tool import SemanticScholarQueryRun
import arxiv
from semanticscholar import SemanticScholar
from github import Github
import re
from state import AgentState
from utils import api_call_with_retry
from tools.router_tools import update_next_node

logger = logging.getLogger(__name__)

def search_web_node(state: AgentState) -> dict:
    """Search the web using Tavily (if API key available) or DuckDuckGo."""
    logger.info("Starting web search...")
    topic = state["topic"]
    
    try:
        from config import settings
        tavily_key = settings.tavily_api_key
        max_results = settings.max_results_per_source
    except:
        import os
        tavily_key = os.getenv("TAVILY_API_KEY")
        max_results = 3
    
    results = []
    
    try:
        if tavily_key:
            logger.debug("Using Tavily for web search")
            from langchain_community.tools.tavily_search import TavilySearchResults
            search = TavilySearchResults(k=max_results)
            raw_results = search.run(topic)
            
            # Use Jina Reader to enhance results if possible
            enhanced_results = []
            import requests
            for res in raw_results:
                url = res.get("url")
                if url and url.startswith("http"):
                    try:
                        # Append r.jina.ai/ to the URL for markdown extraction
                        jina_url = f"https://r.jina.ai/{url}"
                        jina_res = requests.get(jina_url, timeout=5)
                        if jina_res.status_code == 200:
                            res["content"] = jina_res.text[:5000] # Cap content
                            res["url"] = url # Keep original URL
                    except Exception as e_jina:
                        logger.debug(f"Jina extraction failed for {url}: {e_jina}")
                enhanced_results.append(res)
            results = enhanced_results
        else:
            logger.debug("No TAVILY_API_KEY detected. Using DuckDuckGo")
            from langchain_community.tools import DuckDuckGoSearchRun
            search = DuckDuckGoSearchRun()
            res_text = search.run(topic)
            results = [{"content": res_text, "url": "DuckDuckGo"}]
            
        logger.info(f"Web search completed with {len(results)} results")
        
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        results = []
        
    return {"web_research": results, "next_node": update_next_node(state, "web")}

def search_wiki_node(state: AgentState) -> dict:
    """Search Wikipedia for general context."""
    from progress import update_progress
    from metrics import metrics
    
    update_progress("Wikipedia Search")
    logger.info("Starting Wikipedia search...")
    topic = state["topic"]
    results = []
    
    # Detección simple de idioma: si contiene caracteres latinos con tildes o eñes, usamos español.
    # Por defecto inglés para mayor cobertura global.
    lang = "en"
    if re.search(r'[áéíóúÁÉÍÓÚñÑ]', topic):
        lang = "es"
        print("Detectado posible idioma español por caracteres especiales.")
    
    try:
        print(f"Buscando en Wikipedia ({lang})...")
        loader = WikipediaLoader(query=topic, load_max_docs=1, lang=lang)
        # WikipediaLoader doesn't have a direct timeout, but we can wrap the load
        import threading
        def load_with_timeout():
            nonlocal results
            docs = loader.load()
            for doc in docs:
                results.append({
                    "title": doc.metadata.get("title"),
                    "summary": doc.page_content[:1000] + "...",
                    "url": doc.metadata.get("source")
                })
        
        thread = threading.Thread(target=load_with_timeout)
        thread.start()
        thread.join(timeout=10) # 10 seconds timeout
        if thread.is_alive():
            print("⚠️ Wikipedia search timed out.")
        else:
            print(f"✅ Búsqueda en Wikipedia completada.")
    except Exception as e:
        print(f"⚠️ Error en Wikipedia: {e}")
        
    return {"wiki_research": results, "next_node": update_next_node(state, "wiki")}

def translate_to_english(text: str) -> str:
    """Simple translation to English using LLM for technical queries."""
    if not re.search(r'[áéíóúÁÉÍÓÚñÑ]', text):
        return text # Already in English or simple ASCII
        
    logger.info(f"Translating query to English: {text}")
    try:
        from utils import bypass_proxy_for_ollama
        bypass_proxy_for_ollama()
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"), temperature=0)
        prompt = f"Translate the following research topic to English for a technical search on arXiv/GitHub. respond ONLY with the translation: {text}"
        return llm.invoke(prompt).content.strip()
    except:
        return text

def search_arxiv_node(state: AgentState) -> dict:
    """Busca artículos científicos en arXiv usando la librería arxiv directamente."""
    print("\n--- 📄 NODO: BUSCANDO EN ARXIV ---")
    
    # Multilingual strategy: search in English for better density
    original_topic = state["topic"]
    search_topic = translate_to_english(original_topic)
    
    results = []
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=search_topic,
            max_results=3,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        # Limit result iteration to avoid long hangs
        import timeout_decorator # If available or use manual loop
        results_iter = client.results(search)
        for i in range(3):
            try:
                # Use a manual check or small batch if possible
                result = next(results_iter)
                results.append({
                    "title": result.title,
                    "summary": result.summary[:1000] + "...",
                    "authors": ", ".join(author.name for author in result.authors),
                    "url": result.entry_id
                })
            except StopIteration:
                break
            except Exception as e_inner:
                logger.warning(f"Error fetching arXiv result {i}: {e_inner}")
                break
            
        print(f"✅ Búsqueda en arXiv completada. Se encontraron {len(results)} artículos.")
    except Exception as e:
        print(f"⚠️ Error en arXiv: {e}")
        
    return {"arxiv_research": results, "next_node": update_next_node(state, "arxiv")}

def search_scholar_node(state: AgentState) -> dict:
    """Busca artículos académicos en Semantic Scholar usando la librería directamente."""
    print("\n--- 🎓 NODO: BUSCANDO EN SEMANTIC SCHOLAR ---")
    topic = state["topic"]
    results = []
    
    try:
        sch = SemanticScholar()
        # SemanticScholar library can be slow, we add a manual timeout check
        import threading
        def run_search():
            nonlocal search_results
            try:
                # Specify fields to minimize data transfer
                search_results = sch.search_paper(topic, limit=3, fields=['title', 'abstract', 'url', 'year', 'authors'])
            except Exception as e_sch:
                logger.error(f"SemanticScholar API error: {e_sch}")

        search_results = None
        thread = threading.Thread(target=run_search)
        thread.start()
        thread.join(timeout=15) # 15 seconds timeout
        
        if thread.is_alive() or search_results is None:
            logger.warning("Semantic Scholar search timed out or failed.")
            return {"scholar_research": [], "next_node": update_next_node(state, "scholar")}

        # Iteramos con un contador para evitar quedarnos atrapados en PaginatedResults si algo falla
        count = 0
        for paper in search_results:
            if count >= 3:
                break
            authors_list = [author['name'] for author in paper.authors] if paper.authors else []
            results.append({
                "title": paper.title,
                "content": paper.abstract if paper.abstract else "Sin resumen disponible.",
                "url": paper.url,
                "authors": ", ".join(authors_list) if authors_list else "Autor desconocido",
                "year": paper.year
            })
            count += 1
            
        print(f"✅ Búsqueda en Semantic Scholar completada. Se encontraron {len(results)} resultados.")
    except Exception as e:
        print(f"⚠️ Error en Semantic Scholar: {e}")
        
    return {"scholar_research": results, "next_node": update_next_node(state, "scholar")}

def search_github_node(state: AgentState) -> dict:
    """Busca repositorios relevantes en GitHub. Intenta búsqueda amplia si la específica falla."""
    print("\n--- 💻 NODO: BUSCANDO EN GITHUB ---")
    original_topic = state["topic"]
    topic = translate_to_english(original_topic)
    results = []
    
    token = os.getenv("GITHUB_TOKEN")
    try:
        from github import Github
        if token:
            g = Github(token)
        else:
            g = Github() # Public access
            
        import threading
        def run_github_search():
            nonlocal results
            try:
                # Intento 1: Búsqueda específica en Python
                print(f"Buscando repositorios de Python para: {topic}")
                repositories = g.search_repositories(query=f"{topic} language:python", sort="stars", order="desc")
                
                # Comprobar si hay resultados usando totalCount
                if repositories.totalCount == 0:
                    print("No se encontraron repositorios de Python. Intentando búsqueda global...")
                    repositories = g.search_repositories(query=topic, sort="stars", order="desc")
                    
                for i, repo in enumerate(repositories):
                    if i >= 5:
                        break
                    results.append({
                        "name": repo.full_name,
                        "description": repo.description,
                        "url": repo.html_url,
                        "stars": repo.stargazers_count
                    })
            except Exception as e_inner:
                logger.error(f"GitHub inner search failed: {e_inner}")

        thread = threading.Thread(target=run_github_search)
        thread.start()
        thread.join(timeout=20) # 20 seconds for GitHub
        if thread.is_alive():
            logger.warning("GitHub search timed out.")
            results = []
            
        print(f"✅ Búsqueda en GitHub completada ({len(results)} repositorios encontrados).")
    except Exception as e:
        print(f"⚠️ Error en GitHub: {e}")
        
    return {"github_research": results, "next_node": update_next_node(state, "github")}

def search_hn_node(state: AgentState) -> dict:
    """Busca discusiones relevantes en Hacker News."""
    print("\n--- 🧡 NODO: BUSCANDO EN HACKER NEWS ---")
    topic = state["topic"]
    results = []
    
    try:
        from langchain_community.document_loaders import HNLoader
        # Usamos una búsqueda simple en Algolia HN API via el loader si es posible, 
        # o simulamos la búsqueda de historias populares.
        # El HNLoader de LangChain suele cargar por ID o por "new", "top", etc.
        # Para temas específicos, usaremos una aproximación de búsqueda.
        query = topic.replace(" ", "+")
        search_url = f"https://news.ycombinator.com/item?id=" # Solo base
        
        # Como HNLoader no tiene búsqueda directa por query en la versión estándar de LC,
        # usaremos una búsqueda vía API de Algolia rápida.
        import requests
        search_api = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story"
        response = requests.get(search_api, timeout=10)
        data = response.json()
        
        for i, hit in enumerate(data.get('hits', [])):
            if i >= 5:
                break
            results.append({
                "title": hit.get('title'),
                "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "author": hit.get('author'),
                "points": hit.get('points'),
                "num_comments": hit.get('num_comments')
            })
            
        print(f"✅ Búsqueda en Hacker News completada ({len(results)} historias encontradas).")
    except Exception as e:
        print(f"⚠️ Error en Hacker News: {e}")
        
    return {"hn_research": results, "next_node": update_next_node(state, "hn")}

def search_so_node(state: AgentState) -> dict:
    """Busca preguntas técnicas en Stack Overflow."""
    print("\n--- 💙 NODO: BUSCANDO EN STACK OVERFLOW ---")
    topic = state["topic"]
    results = []
    
    try:
        from stackapi import StackAPI
        SITE = StackAPI('stackoverflow')
        
        import threading
        def run_so_search():
            nonlocal results
            try:
                # Buscamos preguntas relacionadas con el tema
                questions = SITE.fetch('search/advanced', q=topic, sort='relevance', order='desc')
                
                for i, item in enumerate(questions.get('items', [])):
                    if i >= 5:
                        break
                    results.append({
                        "title": item.get('title'),
                        "url": item.get('link'),
                        "score": item.get('score'),
                        "is_answered": item.get('is_answered'),
                        "tags": ", ".join(item.get('tags', []))
                    })
            except Exception as e_inner:
                logger.error(f"StackOverflow inner search failed: {e_inner}")

        thread = threading.Thread(target=run_so_search)
        thread.start()
        thread.join(timeout=15) # 15 seconds for SO
        if thread.is_alive():
            logger.warning("Stack Overflow search timed out.")
            results = []
            
        print(f"✅ Búsqueda en Stack Overflow completada ({len(results)} preguntas encontradas).")
    except Exception as e:
        print(f"⚠️ Error en Stack Overflow: {e}")
        
    return {"so_research": results, "next_node": update_next_node(state, "so")}


