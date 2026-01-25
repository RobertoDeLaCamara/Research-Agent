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
import datetime
from ..state import AgentState
from ..utils import api_call_with_retry, get_max_results
from .router_tools import update_next_node

logger = logging.getLogger(__name__)

def search_web_node(state: AgentState) -> dict:
    """Search the web using Tavily (if API key available) or DuckDuckGo."""
    logger.info("Starting web search...")
    topic = state["topic"]
    
    max_results = get_max_results(state)
    
    try:
        from ..config import settings
        tavily_key = settings.tavily_api_key
    except (ImportError, AttributeError):
        import os
        tavily_key = os.getenv("TAVILY_API_KEY")

    results = []
    
    topic = state.get("topic", "")
    queries = state.get("queries", {})
    search_topic = queries.get("en", queries.get("es", topic))
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Validate topic
    if not search_topic or not search_topic.strip():
        logger.warning("Empty search topic. Skipping web search.")
        return {"web_research": [], "next_node": update_next_node(state, "web"), "source_metadata": {"web": {"source_type": "web", "reliability": 3}}}

    # Inject date for timeliness if the user didn't provide one
    if not re.search(r'\b(20\d{2}|19\d{2})\b', search_topic): # Check for a 4-digit year
        search_topic = f"{search_topic} {current_date}"
    
    search_topic = search_topic.strip() # Ensure no leading/trailing spaces
    logger.info(f"Searching web (Tavily) for: {search_topic}")
    
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import requests
    
    def run_web_search():
        nonlocal results
        try:
            if tavily_key:
                logger.debug(f"Using Tavily for web search with query: {search_topic}")
                from langchain_community.tools.tavily_search import TavilySearchResults
                search = TavilySearchResults(k=max_results)
                try:
                    raw_results = search.run(search_topic)
                    # CRITICAL FIX: Ensure raw_results is a list. Tavily can return a string on error.
                    if isinstance(raw_results, str):
                        logger.warning(f"Tavily returned string (possibly error): {raw_results}")
                        # If it looks like a list string, try to parse it, otherwise handle as error/content
                        import ast
                        try:
                            # Sometimes it might be an unparsed list repr
                            parsed = ast.literal_eval(raw_results)
                            if isinstance(parsed, list):
                                raw_results = parsed
                            else:
                                raise ValueError
                        except:
                            # It's a plain string message or error
                            raw_results = [] # Treat as empty/fail rather than fake content
                except Exception as e_tavily:
                     logger.error(f"Tavily search execution failed: {e_tavily}")
                     # Try to access response text if available
                     if hasattr(e_tavily, 'response') and hasattr(e_tavily.response, 'text'):
                         logger.error(f"API Response: {e_tavily.response.text}")
                     raw_results = []
                
                # Use ThreadPoolExecutor to parallelize Jina Reader calls
                def enhance_result(res):
                    if isinstance(res, str): # Defensive check for unexpected string results
                         return {"url": "Unknown", "content": res}
                    
                    url = res.get("url")
                    if url and url.startswith("http"):
                        try:
                            from ..config import settings
                            jina_url = f"https://r.jina.ai/{url}"
                            jina_res = requests.get(jina_url, timeout=settings.content_fetch_timeout)
                            if jina_res.status_code == 200:
                                res["content"] = jina_res.text[:settings.max_content_preview_chars]
                        except Exception:
                            pass
                    return res

                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(enhance_result, raw_results))
            else:
                logger.debug(f"No TAVILY_API_KEY detected. Using DuckDuckGo with query: {search_topic}")
                from langchain_community.tools import DuckDuckGoSearchRun
                search = DuckDuckGoSearchRun()
                res_text = search.run(search_topic)
                results = [{"content": res_text, "url": "DuckDuckGo"}]
        except Exception as e_inner:
            logger.error(f"Inner web search failed: {e_inner}")

    thread = threading.Thread(target=run_web_search)
    thread.start()
    from ..config import settings
    thread.join(timeout=settings.web_search_timeout)
    
    if thread.is_alive():
        logger.warning(f"Web search timed out after {settings.web_search_timeout} seconds.")
        # Proceed with empty results if timed out
        
    logger.info(f"Web search completed with {len(results)} results")
    return {"web_research": results, "next_node": update_next_node(state, "web"), "source_metadata": {"web": {"source_type": "web", "reliability": 3}}}

def search_wiki_node(state: AgentState) -> dict:
    """Search Wikipedia for general context."""
    from ..progress import update_progress
    from ..metrics import metrics
    
    update_progress("Wikipedia Search")
    logger.info("Starting Wikipedia search...")
    topic = state["topic"]
    results = []
    
    # Detección simple de idioma: si contiene caracteres latinos con tildes o eñes, usamos español.
    # Por defecto inglés para mayor cobertura global.
    lang = "en"
    if re.search(r'[áéíóúÁÉÍÓÚñÑ]', topic):
        lang = "es"
        logger.debug("Detected possible Spanish language by special characters.")
    
    try:
        queries = state.get("queries", {})
        search_topic = queries.get(lang, topic)
        
        max_docs = 1 if state.get("research_depth") != "deep" else 3
        logger.info(f"Searching Wikipedia ({lang}) with query: {search_topic}...")
        loader = WikipediaLoader(query=search_topic, load_max_docs=max_docs, lang=lang)
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
            logger.warning("Wikipedia search timed out.")
        else:
            logger.info("Wikipedia search completed.")
    except Exception as e:
        print(f"⚠️ Error en Wikipedia: {e}")
        
    return {"wiki_research": results, "next_node": update_next_node(state, "wiki"), "source_metadata": {"wiki": {"source_type": "official", "reliability": 5}}}

def translate_to_english(text: str) -> str:
    """Simple translation to English using LLM for technical queries."""
    if not re.search(r'[áéíóúÁÉÍÓÚñÑ]', text):
        return text # Already in English or simple ASCII
        
    logger.info(f"Translating query to English: {text}")
    try:
        from ..utils import bypass_proxy_for_ollama
        bypass_proxy_for_ollama()
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen3:14b"), temperature=0, request_timeout=30)
        prompt = f"Translate the following research topic to English for a technical search on arXiv/GitHub. respond ONLY with the translation: {text}"
        return llm.invoke(prompt).content.strip()
    except Exception as e:
        logger.warning(f"Translation failed: {e}, using original text")
        return text

def search_arxiv_node(state: AgentState) -> dict:
    """Busca artículos científicos en arXiv usando la librería arxiv directamente."""
    print("\n--- 📄 NODO: BUSCANDO EN ARXIV ---")
    
    topic = state.get("topic", "")
    queries = state.get("queries", {})
    search_topic = queries.get("en", topic)
    results = []
    
    import threading
    def run_arxiv_search():
        nonlocal results
        try:
            client = arxiv.Client()
            max_results = get_max_results(state)
            search = arxiv.Search(
                query=search_topic,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results_iter = client.results(search)
            for i in range(max_results):
                try:
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
            logger.error(f"ArXiv inner search failed: {e_inner}")

    thread = threading.Thread(target=run_arxiv_search)
    thread.start()
    thread.join(timeout=25) # Increased to 25s for better coverage
    
    if thread.is_alive():
        logger.warning("ArXiv search timed out. Moving on with partial or empty results.")
        # Proceed with what we have
        
    print(f"✅ Búsqueda en arXiv completada. Se encontraron {len(results)} artículos.")
    return {"arxiv_research": results, "next_node": update_next_node(state, "arxiv"), "source_metadata": {"arxiv": {"source_type": "scientific", "reliability": 5}}}

def search_scholar_node(state: AgentState) -> dict:
    """Busca artículos académicos en Semantic Scholar usando la librería directamente."""
    print("\n--- 🎓 NODO: BUSCANDO EN SEMANTIC SCHOLAR ---")
    topic = state["topic"]
    results = []
    
    sch = SemanticScholar()
    max_results = get_max_results(state)
    queries = state.get("queries", {})
    search_topic = queries.get("en", topic)

    import threading
    def run_scholar_search():
        nonlocal results
        try:
            # SemanticScholar library uses lazy loading. 
            # We MUST iterate INSIDE the thread to stay protected by the timeout.
            search_results = sch.search_paper(search_topic, limit=max_results, fields=['title', 'abstract', 'url', 'year', 'authors'])
            
            count = 0
            for paper in search_results:
                if count >= max_results:
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
        except Exception as e_sch:
            logger.error(f"SemanticScholar API error: {e_sch}")

    thread = threading.Thread(target=run_scholar_search)
    thread.start()
    thread.join(timeout=25) # 25 seconds hard timeout for Scholar
    
    if thread.is_alive():
        logger.warning("Semantic Scholar search timed out. Proceeding with collected results so far.")
        
    print(f"✅ Búsqueda en Semantic Scholar completada. Se encontraron {len(results)} resultados.")
    return {"scholar_research": results, "next_node": update_next_node(state, "scholar"), "source_metadata": {"scholar": {"source_type": "scientific", "reliability": 5}}}

def search_github_node(state: AgentState) -> dict:
    """Busca repositorios relevantes en GitHub. Intenta búsqueda amplia si la específica falla."""
    print("\n--- 💻 NODO: BUSCANDO EN GITHUB ---")
    queries = state.get("queries", {})
    topic = queries.get("en", state["topic"])
    results = []
    
    token = os.getenv("GITHUB_TOKEN")
    try:
        from github import Github
        if token:
            g = Github(token)
        else:
            g = Github() # Public access
            
        max_results = get_max_results(state) # Get it here to be safe in closure
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
                    
                from concurrent.futures import ThreadPoolExecutor
                
                def fetch_repo_content(repo):
                    repo_data = {
                        "name": repo.full_name,
                        "description": repo.description,
                        "url": repo.html_url,
                        "stars": repo.stargazers_count
                    }
                    persona = state.get("persona", "general")
                    if persona in ["tech", "pm", "arquitecto", "architect"]:
                        try:
                            readme = repo.get_readme().decoded_content.decode('utf-8')
                            repo_data["content"] = readme[:1500]
                        except Exception as e:
                            logger.debug(f"README not available for {repo.full_name}: {e}")
                            repo_data["content"] = "README no disponible."
                    else:
                        repo_data["content"] = repo.description or "No description."
                    return repo_data

                # Fetch repositories list
                repo_list = []
                for i, repo in enumerate(repositories):
                    if i >= max_results:
                        break
                    repo_list.append(repo)
                
                # Parallel fetch READMEs
                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(fetch_repo_content, repo_list))

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
        
    return {"github_research": results, "next_node": update_next_node(state, "github"), "source_metadata": {"github": {"source_type": "tech", "reliability": 4}}}

def search_hn_node(state: AgentState) -> dict:
    """Busca discusiones relevantes en Hacker News."""
    print("\n--- 🧡 NODO: BUSCANDO EN HACKER NEWS ---")
    queries = state.get("queries", {})
    search_topic = queries.get("en", state["topic"])
    results = []
    
    try:
        from langchain_community.document_loaders import HNLoader
        # Usamos una búsqueda simple en Algolia HN API via el loader si es posible, 
        # o simulamos la búsqueda de historias populares.
        # El HNLoader de LangChain suele cargar por ID o por "new", "top", etc.
        # Para temas específicos, usaremos una aproximación de búsqueda.
        query = search_topic.replace(" ", "+")
        search_url = f"https://news.ycombinator.com/item?id=" # Solo base
        
        # Como HNLoader no tiene búsqueda directa por query en la versión estándar de LC,
        # usaremos una búsqueda vía API de Algolia rápida.
        import requests
        search_api = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story"
        response = requests.get(search_api, timeout=10)
        data = response.json()
        
        max_results = get_max_results(state)
        for i, hit in enumerate(data.get('hits', [])):
            if i >= max_results:
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
        
    return {"hn_research": results, "next_node": update_next_node(state, "hn"), "source_metadata": {"hn": {"source_type": "tech_community", "reliability": 4}}}

def search_so_node(state: AgentState) -> dict:
    """Busca preguntas técnicas en Stack Overflow."""
    print("\n--- 💙 NODO: BUSCANDO EN STACK OVERFLOW ---")
    queries = state.get("queries", {})
    search_topic = queries.get("en", state["topic"])
    results = []
    
    try:
        from stackapi import StackAPI
        SITE = StackAPI('stackoverflow')
        
        import threading
        def run_so_search():
            nonlocal results
            try:
                # Buscamos preguntas relacionadas con el tema
                questions = SITE.fetch('search/advanced', q=search_topic, sort='relevance', order='desc', filter='withbody')
                
                max_results = get_max_results(state)
                for i, item in enumerate(questions.get('items', [])):
                    if i >= max_results:
                        break
                    
                    # Phase 6: Deep content for SO only if relevant
                    persona = state.get("persona", "general")
                    body = item.get('body', '')
                    if persona in ["tech", "pm", "arquitecto", "architect"]:
                        content = body[:1000] # Reduced from 2000
                    else:
                        content = item.get('title') # Just the title as summary
                        
                    results.append({
                        "title": item.get('title'),
                        "url": item.get('link'),
                        "score": item.get('score'),
                        "is_answered": item.get('is_answered'),
                        "tags": ", ".join(item.get('tags', [])),
                        "content": content
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
        
    return {"so_research": results, "next_node": update_next_node(state, "so"), "source_metadata": {"so": {"source_type": "tech_qa", "reliability": 4}}}


