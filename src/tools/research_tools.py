# src/tools/research_tools.py

import os
from typing import List, TypedDict
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import WikipediaLoader
from langchain_community.tools.semanticscholar.tool import SemanticScholarQueryRun
import arxiv
from semanticscholar import SemanticScholar
from github import Github
import re

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

def search_web_node(state: AgentState) -> dict:
    """Busca en la web usando Tavily (si hay API key) o DuckDuckGo."""
    print("\n--- 🌐 NODO: BUSCANDO EN LA WEB ---")
    topic = state["topic"]
    
    tavily_key = os.getenv("TAVILY_API_KEY")
    results = []
    
    try:
        if tavily_key:
            print("Usando Tavily para la búsqueda...")
            search = TavilySearchResults(k=3)
            results = search.run(topic)
        else:
            print("No se detectó TAVILY_API_KEY. Usando DuckDuckGo...")
            search = DuckDuckGoSearchRun()
            res_text = search.run(topic)
            results = [{"content": res_text, "url": "DuckDuckGo"}]
            
        print(f"✅ Búsqueda web completada.")
    except Exception as e:
        print(f"⚠️ Error en búsqueda web: {e}")
        
    return {"web_research": results}

def search_wiki_node(state: AgentState) -> dict:
    """Busca en Wikipedia para obtener un contexto general. Detecta idioma automáticamente."""
    print("\n--- 📖 NODO: BUSCANDO EN WIKIPEDIA ---")
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
        docs = loader.load()
        for doc in docs:
            results.append({
                "title": doc.metadata.get("title"),
                "summary": doc.page_content[:1000] + "...",
                "url": doc.metadata.get("source")
            })
        print(f"✅ Búsqueda en Wikipedia completada.")
    except Exception as e:
        print(f"⚠️ Error en Wikipedia: {e}")
        
    return {"wiki_research": results}

def search_arxiv_node(state: AgentState) -> dict:
    """Busca artículos científicos en arXiv usando la librería arxiv directamente."""
    print("\n--- 📄 NODO: BUSCANDO EN ARXIV ---")
    topic = state["topic"]
    results = []
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=topic,
            max_results=3,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        for result in client.results(search):
            results.append({
                "title": result.title,
                "summary": result.summary[:1000] + "...",
                "authors": ", ".join(author.name for author in result.authors),
                "url": result.entry_id
            })
            
        print(f"✅ Búsqueda en arXiv completada. Se encontraron {len(results)} artículos.")
    except Exception as e:
        print(f"⚠️ Error en arXiv: {e}")
        
    return {"arxiv_research": results}

def search_scholar_node(state: AgentState) -> dict:
    """Busca artículos académicos en Semantic Scholar usando la librería directamente."""
    print("\n--- 🎓 NODO: BUSCANDO EN SEMANTIC SCHOLAR ---")
    topic = state["topic"]
    results = []
    
    try:
        sch = SemanticScholar()
        # Pedimos campos específicos para evitar sobrecarga y posibles hangs
        search_results = sch.search_paper(topic, limit=3, fields=['title', 'abstract', 'url', 'year', 'authors'])
        
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
        
    return {"scholar_research": results}

def search_github_node(state: AgentState) -> dict:
    """Busca repositorios relevantes en GitHub. Intenta búsqueda amplia si la específica falla."""
    print("\n--- 💻 NODO: BUSCANDO EN GITHUB ---")
    topic = state["topic"]
    results = []
    
    token = os.getenv("GITHUB_TOKEN")
    try:
        from github import Github
        if token:
            g = Github(token)
        else:
            g = Github() # Public access
            
        # Intento 1: Búsqueda específica en Python
        print(f"Buscando repositorios de Python para: {topic}")
        repositories = g.search_repositories(query=f"{topic} language:python", sort="stars", order="desc")
        
        # Comprobar si hay resultados usando totalCount para evitar errores de slice
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
            
        print(f"✅ Búsqueda en GitHub completada ({len(results)} repositorios encontrados).")
    except Exception as e:
        print(f"⚠️ Error en GitHub: {e}")
        
    return {"github_research": results}

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
        response = requests.get(search_api)
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
        
    return {"hn_research": results}

def search_so_node(state: AgentState) -> dict:
    """Busca preguntas técnicas en Stack Overflow."""
    print("\n--- 💙 NODO: BUSCANDO EN STACK OVERFLOW ---")
    topic = state["topic"]
    results = []
    
    try:
        from stackapi import StackAPI
        SITE = StackAPI('stackoverflow')
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
            
        print(f"✅ Búsqueda en Stack Overflow completada ({len(results)} preguntas encontradas).")
    except Exception as e:
        print(f"⚠️ Error en Stack Overflow: {e}")
        
    return {"so_research": results}


