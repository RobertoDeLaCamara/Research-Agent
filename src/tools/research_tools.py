# src/tools/research_tools.py

import os
from typing import List, TypedDict
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import WikipediaLoader, ArxivLoader
from langchain_community.tools.semanticscholar.tool import SemanticScholarQueryRun
from github import Github

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
    """Busca en Wikipedia para obtener un contexto general."""
    print("\n--- 📖 NODO: BUSCANDO EN WIKIPEDIA ---")
    topic = state["topic"]
    results = []
    
    try:
        loader = WikipediaLoader(query=topic, load_max_docs=1, lang="es")
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
    """Busca artículos científicos en arXiv."""
    print("\n--- 📄 NODO: BUSCANDO EN ARXIV ---")
    topic = state["topic"]
    results = []
    
    try:
        loader = ArxivLoader(query=topic, load_max_docs=3)
        docs = loader.load()
        for doc in docs:
            results.append({
                "title": doc.metadata.get("Title"),
                "summary": doc.page_content[:1000] + "...",
                "authors": doc.metadata.get("Authors")
            })
        print(f"✅ Búsqueda en arXiv completada.")
    except Exception as e:
        print(f"⚠️ Error en arXiv: {e}")
        
    return {"arxiv_research": results}

def search_scholar_node(state: AgentState) -> dict:
    """Busca artículos académicos en Semantic Scholar."""
    print("\n--- 🎓 NODO: BUSCANDO EN SEMANTIC SCHOLAR ---")
    topic = state["topic"]
    results = []
    
    try:
        scholar = SemanticScholarQueryRun()
        res_text = scholar.run(topic)
        results = [{"content": res_text}]
        print(f"✅ Búsqueda en Semantic Scholar completada.")
    except Exception as e:
        print(f"⚠️ Error en Semantic Scholar: {e}")
        
    return {"scholar_research": results}

def search_github_node(state: AgentState) -> dict:
    """Busca repositorios relevantes en GitHub."""
    print("\n--- 💻 NODO: BUSCANDO EN GITHUB ---")
    topic = state["topic"]
    results = []
    
    token = os.getenv("GITHUB_TOKEN")
    try:
        if token:
            g = Github(token)
        else:
            g = Github() # Public access
            
        repositories = g.search_repositories(query=f"{topic} language:python", sort="stars", order="desc")
        
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


