# src/tools/research_tools.py

import logging
from github import Auth, Github
import arxiv
from semanticscholar import SemanticScholar
import re
import datetime
from ..credentials import get_credential
from ..state import AgentState
from ..utils import get_max_results
from .source_loaders import duckduckgo_search, is_bot_block_or_stub, wikipedia_pages
from .router_tools import update_next_node

logger = logging.getLogger(__name__)


def search_web_node(state: AgentState) -> dict:
    """Search the web with DuckDuckGo (ddgs, no API key) and fetch each page through Jina Reader."""
    logger.info("Starting web search...")
    topic = state["topic"]

    max_results = get_max_results(state)

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
        
    logger.info(f"Searching web for: {search_topic}")
    
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import requests

    container = {"data": []}
    def run_web_search():
        try:
            raw_results = duckduckgo_search(search_topic, max_results=max_results)

            # Replace the search snippet with the page text (Jina Reader), in parallel
            def enhance_result(res):
                url = res.get("url")
                if url and url.startswith("http"):
                    try:
                        from ..config import settings
                        jina_url = f"https://r.jina.ai/{url}"
                        jina_res = requests.get(jina_url, timeout=settings.content_fetch_timeout)
                        if jina_res.status_code == 200 and not is_bot_block_or_stub(jina_res.text, res.get("title", "")):
                            res["content"] = jina_res.text[:settings.max_content_preview_chars]
                    except Exception:
                        pass
                return res

            with ThreadPoolExecutor(max_workers=5) as executor:
                enhanced = list(executor.map(enhance_result, raw_results))
            container["data"] = [
                r for r in enhanced
                if not is_bot_block_or_stub(r.get("content", ""), r.get("title", ""))
            ]
        except Exception as e_inner:
            logger.error(f"Inner web search failed: {e_inner}")

    thread = threading.Thread(target=run_web_search, daemon=True)
    thread.start()
    from ..config import settings
    thread.join(timeout=settings.web_search_timeout)
    
    if thread.is_alive():
        logger.warning(f"Web search timed out after {settings.web_search_timeout} seconds.")
    else:
        results = container["data"]

    logger.info(f"Web search completed with {len(results)} results")
    return {"web_research": results, "next_node": update_next_node(state, "web"), "source_metadata": {"web": {"source_type": "web", "reliability": 3}}}


def search_wiki_node(state: AgentState) -> dict:
    """Search Wikipedia for general context."""
    from ..progress import update_progress
    
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
        # The wikipedia library has no timeout of its own, so the load runs in a thread
        import threading
        container = {"data": []}
        def load_with_timeout():
            for page in wikipedia_pages(search_topic, lang=lang, max_docs=max_docs):
                container["data"].append({
                    "title": page["title"],
                    "summary": page["content"][:1000] + "...",
                    "url": page["url"]
                })

        thread = threading.Thread(target=load_with_timeout, daemon=True)
        thread.start()
        thread.join(timeout=10) # 10 seconds timeout
        if thread.is_alive():
            logger.warning("Wikipedia search timed out.")
        else:
            results = container["data"]
            logger.info("Wikipedia search completed.")
    except Exception as e:
        logger.warning("wikipedia_search_failed", exc_info=e)

    return {"wiki_research": results, "next_node": update_next_node(state, "wiki"), "source_metadata": {"wiki": {"source_type": "official", "reliability": 5}}}


_ARXIV_STOPWORDS = frozenset({
    "de", "del", "la", "las", "el", "los", "en", "un", "una", "unos", "unas",
    "por", "para", "con", "sin", "sobre", "entre", "hacia", "como", "mas", "más",
    "estado", "arte", "evolucion", "evolución", "estandarizacion", "estandarización",
    "the", "and", "or", "in", "on", "of", "for", "to", "with", "by", "from", "at",
    "as", "into", "about", "state", "art", "evolution", "standardization",
    "overview", "review", "survey", "tutorial", "study", "analysis",
})

_HEP_COLLISION_RE = re.compile(
    r"\b(BESIII|BEPCII|charmonium|fb\^\{?-1\}?|GeV/c|MeV/c|born cross section)s?\b"
    r"|e\^\+?\{?\+\}?e\^\-?\{?\-\}?\s*\\(to|rightarrow)",
    re.I,
)
_PHYSICS_TOPIC_RE = re.compile(
    r"\b(physics|f[ií]sica|particle|quark|meson|baryon|hadron|charmonium|besiii|collider|gev|mev|positron|electron)\b",
    re.I,
)
_MAX_ARXIV_AUTHORS = 5


def sanitize_arxiv_query(raw_query: str) -> str:
    """Clean a free-text topic for the arXiv API.

    Strips colons (which arXiv's Lucene parser misinterprets as field prefixes like ``6G:``)
    and removes Spanish/English filler words so the query targets core technical concepts.
    """
    if not raw_query or not raw_query.strip():
        return ""
    # Replace colons and punctuation with spaces
    cleaned = re.sub(r"[:;,/\\()\[\]{}'\"!\?]+", " ", raw_query)
    tokens = []
    for tok in cleaned.split():
        low = tok.lower().strip("-")
        if len(low) <= 1 or low in _ARXIV_STOPWORDS:
            continue
        tokens.append(tok)
    if not tokens:
        return re.sub(r"[:;,]+", " ", raw_query).strip()
    return " ".join(tokens)


def format_arxiv_authors(authors, max_authors: int = _MAX_ARXIV_AUTHORS) -> str:
    """Format arXiv author list, capping huge collaborations (e.g. BESIII 500+ authors) with 'et al.'."""
    names = [getattr(a, "name", str(a)).strip() for a in (authors or []) if getattr(a, "name", str(a)).strip()]
    if not names:
        return "Unknown"
    if len(names) > max_authors:
        return ", ".join(names[:max_authors]) + " et al."
    return ", ".join(names)


def is_arxiv_result_relevant(title: str, summary: str, query: str) -> bool:
    """Filter out off-topic arXiv hits (such as high-energy particle physics papers matching author initials)."""
    combined = f"{title or ''} {summary or ''}"
    if not combined.strip():
        return False
    # Reject high-energy particle physics collision papers unless the query is actually about physics
    if _HEP_COLLISION_RE.search(combined) and not _PHYSICS_TOPIC_RE.search(query or ""):
        return False
    sanitized = sanitize_arxiv_query(query or "").lower()
    keywords = [
        w for w in re.findall(r"[a-z0-9áéíóúñ]{2,}", sanitized)
        if w not in _ARXIV_STOPWORDS and w not in {"test", "topic", "query", "arxiv"}
    ]
    if not keywords:
        return True
    combined_lower = combined.lower()
    return any(kw in combined_lower for kw in keywords)


def search_arxiv_node(state: AgentState) -> dict:
    """Busca artículos científicos en arXiv usando la librería arxiv directamente."""
    logger.info("arxiv_search_started")

    topic = state.get("topic", "")
    queries = state.get("queries", {})
    raw_search_topic = queries.get("en", topic)
    search_topic = sanitize_arxiv_query(raw_search_topic)
    results = []

    import threading
    container = {"data": []}
    def run_arxiv_search():
        max_results = get_max_results(state)
        fetch_limit = max(max_results * 2, 10)
        try:
            client = arxiv.Client(page_size=fetch_limit, delay_seconds=1.0)
            search = arxiv.Search(
                query=search_topic,
                max_results=fetch_limit,
                sort_by=arxiv.SortCriterion.Relevance
            )
            results_iter = client.results(search)
            for _ in range(fetch_limit):
                if len(container["data"]) >= max_results:
                    break
                try:
                    result = next(results_iter)
                    title = (result.title or "").strip()
                    summary = (result.summary or "").strip()
                    if not is_arxiv_result_relevant(title, summary, raw_search_topic):
                        logger.debug(f"Skipping irrelevant arXiv result: {title[:80]}")
                        continue
                    container["data"].append({
                        "title": title,
                        "summary": summary[:1000] + "...",
                        "authors": format_arxiv_authors(result.authors),
                        "url": result.entry_id
                    })
                except StopIteration:
                    break
        except Exception as e_inner:
            logger.error(f"ArXiv inner search failed: {e_inner}")

    thread = threading.Thread(target=run_arxiv_search, daemon=True)
    thread.start()
    thread.join(timeout=12) # 12s timeout

    if thread.is_alive():
        logger.warning("ArXiv search timed out. Moving on with partial or empty results.")
    else:
        results = container["data"]
        # Proceed with what we have

    logger.info(f"arxiv_search_completed results_count={len(results)}")
    return {"arxiv_research": results, "next_node": update_next_node(state, "arxiv"), "source_metadata": {"arxiv": {"source_type": "scientific", "reliability": 5}}}


def search_scholar_node(state: AgentState) -> dict:
    """Busca artículos académicos en Semantic Scholar usando la librería directamente."""
    logger.info("scholar_search_started")
    topic = state["topic"]
    results = []

    sch = SemanticScholar(timeout=10, retry=False)
    max_results = get_max_results(state)
    queries = state.get("queries", {})
    search_topic = queries.get("en", topic)

    import threading
    container = {"data": []}
    def run_scholar_search():
        try:
            search_results = sch.search_paper(search_topic, limit=max_results, fields=['title', 'abstract', 'url', 'year', 'authors'])
            count = 0
            for paper in search_results:
                if count >= max_results:
                    break
                authors_list = [author['name'] for author in paper.authors] if paper.authors else []
                container["data"].append({
                    "title": paper.title,
                    "content": paper.abstract if paper.abstract else "Sin resumen disponible.",
                    "url": paper.url,
                    "authors": ", ".join(authors_list) if authors_list else "Autor desconocido",
                    "year": paper.year
                })
                count += 1
        except Exception as e_sch:
            logger.error(f"SemanticScholar API error: {e_sch}")

    thread = threading.Thread(target=run_scholar_search, daemon=True)
    thread.start()
    thread.join(timeout=25) # 25 seconds hard timeout for Scholar

    if thread.is_alive():
        logger.warning("Semantic Scholar search timed out. Proceeding with collected results so far.")
    else:
        results = container["data"]

    logger.info(f"scholar_search_completed results_count={len(results)}")
    return {"scholar_research": results, "next_node": update_next_node(state, "scholar"), "source_metadata": {"scholar": {"source_type": "scientific", "reliability": 5}}}


def search_github_node(state: AgentState) -> dict:
    """Busca repositorios relevantes en GitHub. Intenta búsqueda amplia si la específica falla."""
    logger.info("github_search_started")
    queries = state.get("queries", {})
    topic = queries.get("en", state["topic"])
    results = []

    token = get_credential("GITHUB_TOKEN")
    try:
        if token:
            g = Github(auth=Auth.Token(token))
        else:
            g = Github() # Public access
            
        max_results = get_max_results(state) # Get it here to be safe in closure
        import threading
        container = {"data": []}
        def run_github_search():
            try:
                # Intento 1: Búsqueda específica en Python
                logger.info(f"github_python_search topic={topic}")
                repositories = g.search_repositories(query=f"{topic} language:python", sort="stars", order="desc")

                # Comprobar si hay resultados usando totalCount
                if repositories.totalCount == 0:
                    logger.info("github_fallback_to_global_search")
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
                    container["data"] = list(executor.map(fetch_repo_content, repo_list))

            except Exception as e_inner:
                logger.error(f"GitHub inner search failed: {e_inner}")

        thread = threading.Thread(target=run_github_search, daemon=True)
        thread.start()
        thread.join(timeout=20) # 20 seconds for GitHub
        if thread.is_alive():
            logger.warning("GitHub search timed out.")
        else:
            results = container["data"]

        logger.info(f"github_search_completed results_count={len(results)}")
    except Exception as e:
        logger.warning("github_search_failed", exc_info=e)

    return {"github_research": results, "next_node": update_next_node(state, "github"), "source_metadata": {"github": {"source_type": "tech", "reliability": 4}}}


def search_hn_node(state: AgentState) -> dict:
    """Busca discusiones relevantes en Hacker News."""
    logger.info("hn_search_started")
    queries = state.get("queries", {})
    search_topic = queries.get("en", state["topic"])
    results = []

    try:
        # Usamos una búsqueda simple en Algolia HN API via el loader si es posible,
        # o simulamos la búsqueda de historias populares.
        # El HNLoader de LangChain suele cargar por ID o por "new", "top", etc.
        # Para temas específicos, usaremos una aproximación de búsqueda.
        query = search_topic.replace(" ", "+")

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

        logger.info(f"hn_search_completed results_count={len(results)}")
    except Exception as e:
        logger.warning("hn_search_failed", exc_info=e)

    return {"hn_research": results, "next_node": update_next_node(state, "hn"), "source_metadata": {"hn": {"source_type": "tech_community", "reliability": 4}}}


def search_so_node(state: AgentState) -> dict:
    """Busca preguntas técnicas en Stack Overflow."""
    logger.info("stackoverflow_search_started")
    queries = state.get("queries", {})
    search_topic = queries.get("en", state["topic"])
    results = []

    try:
        from stackapi import StackAPI
        SITE = StackAPI('stackoverflow')

        import threading
        container = {"data": []}
        def run_so_search():
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

                    container["data"].append({
                        "title": item.get('title'),
                        "url": item.get('link'),
                        "score": item.get('score'),
                        "is_answered": item.get('is_answered'),
                        "tags": ", ".join(item.get('tags', [])),
                        "content": content
                    })
            except Exception as e_inner:
                logger.error(f"StackOverflow inner search failed: {e_inner}")

        thread = threading.Thread(target=run_so_search, daemon=True)
        thread.start()
        thread.join(timeout=15) # 15 seconds for SO
        if thread.is_alive():
            logger.warning("Stack Overflow search timed out.")
        else:
            results = container["data"]

        logger.info(f"stackoverflow_search_completed results_count={len(results)}")
    except Exception as e:
        logger.warning("stackoverflow_search_failed", exc_info=e)

    return {"so_research": results, "next_node": update_next_node(state, "so"), "source_metadata": {"so": {"source_type": "tech_qa", "reliability": 4}}}
