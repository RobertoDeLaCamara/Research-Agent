import streamlit as st # noqa: E402
# Force push timestamp: 2026-01-25
import sys
import os
import time
import asyncio

# Fix for "Can't patch loop of type <class 'uvloop.Loop'>"
# LangChain/NestAsyncio requires standard asyncio loop, but Uvicorn/Streamlit might set uvloop.
try:
    import uvloop  # noqa: F401
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except ImportError:
    pass

import nest_asyncio
nest_asyncio.apply()


# Add project root to sys.path to ensure 'src' package is resolvable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.logging_config import setup_logging # noqa: E402
setup_logging()

from src.agent import app # noqa: E402
import streamlit.components.v1 as components # noqa: E402
from src.db_manager import get_recent_sessions, load_session, clear_history # noqa: E402
from src.i18n import T # noqa: E402

# Configuración de la página
st.set_page_config(
    page_title="Research-Agent Dashboard",
    page_icon="🔍",
    layout="wide",
)

# Estilos personalizados
st.markdown("""
    <style>
    .main {
        background-color: #f8fafc;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #2563eb;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1e40af;
        border-color: #1e40af;
    }
    .status-text {
        font-size: 0.9em;
        color: #64748b;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Language initialisation (must happen before sidebar renders) ───────────────
if "lang" not in st.session_state:
    st.session_state.lang = "es"

# Sidebar
with st.sidebar:
    # Language toggle — top of sidebar
    lang_col1, lang_col2 = st.columns(2)
    with lang_col1:
        if st.button("🇪🇸 Español", use_container_width=True,
                     type="primary" if st.session_state.lang == "es" else "secondary"):
            st.session_state.lang = "es"
            st.rerun()
    with lang_col2:
        if st.button("🇬🇧 English", use_container_width=True,
                     type="primary" if st.session_state.lang == "en" else "secondary"):
            st.session_state.lang = "en"
            st.rerun()

    lang = st.session_state.lang
    _ = T[lang]  # shorthand for current language strings

    st.divider()
    st.title(_["sidebar_title"])
    st.info(_["sidebar_info"])

    @st.cache_data(ttl=60)
    def _get_ollama_models(base_url: str) -> list[str]:
        try:
            import requests
            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            models = [m["name"] for m in resp.json().get("models", [])]
            return models if models else [os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")]
        except Exception:
            return [os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")]

    available_models = _get_ollama_models(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    current_model = os.environ.get("OLLAMA_MODEL", available_models[0])
    default_index = available_models.index(current_model) if current_model in available_models else 0

    llm_model = st.selectbox(
        _["llm_model_label"],
        available_models,
        index=default_index
    )

    st.write(_["active_sources"])
    sources = {
        "wiki": st.checkbox("Wikipedia", value=True),
        "web": st.checkbox("Web Search (Tavily)", value=True),
        "arxiv": st.checkbox("arXiv", value=True),
        "scholar": st.checkbox("Semantic Scholar", value=True),
        "github": st.checkbox("GitHub", value=True),
        "hn": st.checkbox("Hacker News", value=True),
        "so": st.checkbox("Stack Overflow", value=True),
        "youtube": st.checkbox("YouTube Summaries", value=True),
        "reddit": st.checkbox("Reddit", value=True)
    }

    # Filter only selected sources
    selected_sources = [k for k, v in sources.items() if v]

    st.write(_["depth_header"])
    depth_options = [_["depth_quick"], _["depth_standard"], _["depth_deep"]]
    depth_mode = st.radio(
        _["depth_label"],
        depth_options,
        index=1,
        help=_["depth_help"]
    )
    research_depth = ["quick", "standard", "deep"][depth_options.index(depth_mode)]

    st.write(_["persona_header"])
    persona_labels = [
        _["persona_general"], _["persona_business"], _["persona_tech"],
        _["persona_academic"], _["persona_pm"], _["persona_news"],
    ]
    persona_codes = ["general", "business", "tech", "academic", "pm", "news_editor"]
    persona_mode = st.selectbox(
        _["persona_label"],
        persona_labels,
        index=0,
        help=_["persona_help"]
    )
    persona = persona_codes[persona_labels.index(persona_mode)]

    st.write(_["time_header"])
    last_24h = st.checkbox(_["time_24h"], value=False, help=_["time_24h_help"])
    time_range = "d" if last_24h else None

    st.write(_["local_header"])
    use_rag = st.checkbox(_["local_rag_checkbox"], value=False, help=_["local_rag_help"])

    uploaded_files = st.file_uploader(_["upload_label"], type=["pdf", "txt"], accept_multiple_files=True)
    if uploaded_files:
        kb_path = "./knowledge_base"
        if not os.path.exists(kb_path):
            os.makedirs(kb_path)
        for uploaded_file in uploaded_files:
            with open(os.path.join(kb_path, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"✅ " + _["upload_success"].format(n=len(uploaded_files)))

    st.divider()
    st.write(_["history_header"])
    recent_sessions = get_recent_sessions(limit=10)
    if recent_sessions:
        session_options = [_["history_select_placeholder"]] + [f"{s[3][:16]} | {s[1]}" for s in recent_sessions]
        selected_session_label = st.selectbox(_["history_load_label"], session_options)

        if selected_session_label != _["history_select_placeholder"]:
            if st.button(_["history_load_btn"]):
                session_idx = session_options.index(selected_session_label) - 1
                session_id = recent_sessions[session_idx][0]
                loaded_state = load_session(session_id)
                if loaded_state:
                    st.session_state.agent_state = loaded_state
                    st.session_state.last_topic = loaded_state.get("topic", _["history_select_placeholder"])
                    # Map 'report' from state to 'report_html' for UI
                    st.session_state.report_html = loaded_state.get("report", "")
                    st.session_state.investigation_done = True
                    st.success(_["history_loaded"].format(topic=st.session_state.last_topic))
                    st.rerun()
    else:
        st.write(_["history_empty"])

    if st.button(_["history_clear_btn"], type="secondary", use_container_width=True):
        if clear_history():
            st.success(_["history_cleared"])
            st.rerun()

    # HF Spaces: show API key panel when running as a Space
    if os.environ.get("SPACE_ID"):
        st.divider()
        st.write(_["hf_key_header"])
        st.caption(_["hf_key_caption"])

        _PROVIDERS = {
            "Groq (free — llama-3.1-8b)": (
                "https://api.groq.com/openai/v1",
                "llama-3.1-8b-instant",
                "Get free key → console.groq.com",
            ),
            "Google Gemini (free — flash)": (
                "https://generativelanguage.googleapis.com/v1beta/openai",
                "gemini-1.5-flash",
                "Get free key → aistudio.google.com",
            ),
            "OpenAI": (
                "https://api.openai.com/v1",
                "gpt-4o-mini",
                "Requires paid account",
            ),
        }

        provider_name = st.selectbox("Provider", list(_PROVIDERS.keys()))
        base_url, default_model, hint = _PROVIDERS[provider_name]
        st.caption(hint)

        api_key_input = st.text_input("API Key", type="password", placeholder="Paste your key here")
        custom_model = st.text_input("Model (optional override)", placeholder=default_model)

        if st.button(_["hf_key_apply"], use_container_width=True):
            if api_key_input:
                os.environ["OPENAI_API_KEY"] = api_key_input
                os.environ["OLLAMA_BASE_URL"] = base_url
                os.environ["OLLAMA_MODEL"] = custom_model.strip() or default_model
                st.success(_["hf_key_success"])
            else:
                st.error(_["hf_key_error"])

        if not os.environ.get("OPENAI_API_KEY"):
            st.warning(_["hf_key_warning"])

    # Optional API keys (always visible)
    st.divider()
    with st.expander(_["opt_keys_header"]):
        st.caption(_["opt_keys_caption"])

        tavily_input = st.text_input(
            _["opt_keys_tavily"], type="password",
            placeholder=_["opt_keys_tavily_hint"],
            value=os.environ.get("TAVILY_API_KEY", ""),
        )
        github_input = st.text_input(
            _["opt_keys_github"], type="password",
            placeholder=_["opt_keys_github_hint"],
            value=os.environ.get("GITHUB_TOKEN", ""),
        )
        youtube_input = st.text_input(
            _["opt_keys_youtube"], type="password",
            placeholder=_["opt_keys_youtube_hint"],
            value=os.environ.get("YOUTUBE_API_KEY", ""),
        )

        if st.button(_["opt_keys_apply"], use_container_width=True):
            if tavily_input:
                os.environ["TAVILY_API_KEY"] = tavily_input
            if github_input:
                os.environ["GITHUB_TOKEN"] = github_input
            if youtube_input:
                os.environ["YOUTUBE_API_KEY"] = youtube_input
            st.success(_["opt_keys_success"])

# --- Inicialización de Session State ---
if "investigation_done" not in st.session_state:
    st.session_state.investigation_done = False
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""
if "report_html" not in st.session_state:
    st.session_state.report_html = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None

lang = st.session_state.lang
_ = T[lang]

# Auto-detectar reportes existentes al iniciar
if not st.session_state.investigation_done:
    if os.path.exists("reports/reporte_final.html"):
        with open("reports/reporte_final.html", "r", encoding="utf-8") as f:
            st.session_state.report_html = f.read()
        st.session_state.investigation_done = True
        st.session_state.last_topic = "__saved_report__"

# Main UI
st.title("🔍 Research-Agent")
st.subheader(_["page_subtitle"])

topic = st.text_input(_["topic_label"], placeholder=_["topic_placeholder"])

if st.button(_["start_btn"]):
    if not topic:
        st.warning(_["topic_warning"])
    else:
        # Clear previous state to ensure clean start
        st.session_state.investigation_done = False
        st.session_state.report_html = ""
        st.session_state.agent_state = None

        with st.status(_["status_running"], expanded=True) as status:
            try:
                # Actualizar variables de entorno para el modelo seleccionado
                os.environ["OLLAMA_MODEL"] = llm_model

                # Pass selected sources and depth to the agent
                inputs = {
                    "topic": topic,
                    "original_topic": topic, # Preserve original for titles
                    "research_depth": research_depth,
                    "persona": persona,
                    "time_range": time_range
                }

                plan = selected_sources.copy()
                if use_rag:
                    plan.insert(0, "local_rag")

                if plan:
                    inputs["research_plan"] = plan
                    inputs["next_node"] = plan[0]

                node_messages = {
                    "initialize_state": _["node_initialize_state"],
                    "plan_research": _["node_plan_research"],
                    "search_videos": _["node_search_videos"],
                    "summarize_videos": _["node_summarize_videos"],
                    "search_web": _["node_search_web"],
                    "search_wiki": _["node_search_wiki"],
                    "search_arxiv": _["node_search_arxiv"],
                    "search_scholar": _["node_search_scholar"],
                    "search_github": _["node_search_github"],
                    "search_hn": _["node_search_hn"],
                    "search_so": _["node_search_so"],
                    "search_reddit": _["node_search_reddit"],
                    "local_rag": _["node_local_rag"],
                    "consolidate_research": _["node_consolidate_research"],
                    "evaluate_research": _["node_evaluate_research"],
                    "generate_report": _["node_generate_report"],
                    "send_email": _["node_send_email"],
                }

                # Streaming execution with Threading and Queue to allow Progress Polling
                import threading
                import queue
                import json

                final_state = inputs.copy()
                status_container = st.empty()
                rag_progress_bar = st.empty() # Placeholder for progress bar

                # Queue for agent events
                event_q = queue.Queue()

                def run_agent_in_thread(inputs_dict, q):
                    try:
                        for chunk in app.stream(inputs_dict, config={"recursion_limit": 100}):
                            q.put(chunk)
                    except Exception as e:
                        q.put({"error": str(e)})
                    finally:
                        q.put(None) # Sentinel

                # Start Agent Thread
                agent_thread = threading.Thread(target=run_agent_in_thread, args=(inputs, event_q))
                agent_thread.start()

                # Main Loop: consume events AND poll RAG status
                rag_status_file = "/app/data/rag_status.json"

                while True:
                    # 1. Poll Queue for Agent Events
                    try:
                        while True:
                            # Non-blocking get all available items
                            chunk = event_q.get_nowait()

                            if chunk is None: # Sentinel
                                agent_thread.join()
                                break

                            if "error" in chunk and isinstance(chunk, dict) and len(chunk) == 1:
                                raise Exception(chunk["error"])

                            for node_name, state_update in chunk.items():
                                if isinstance(state_update, dict):
                                    final_state.update(state_update)

                                # UI Updates for Completed Nodes
                                completed_msg = node_messages.get(
                                    node_name,
                                    _["node_fallback"].format(node=node_name)
                                )
                                st.write(f"✅ {completed_msg}")
                                # Clean up progress bar when RAG finishes
                                if node_name == "local_rag":
                                     rag_progress_bar.empty()

                                next_node = state_update.get("next_node") if state_update else None
                                if next_node and next_node != "END":
                                    next_msg = node_messages.get(
                                        next_node,
                                        _["node_fallback"].format(node=next_node)
                                    )
                                    status_container.info(f"⏳ {next_msg}")
                                else:
                                    status_container.empty()

                    except queue.Empty:
                        pass

                    if not agent_thread.is_alive() and event_q.empty():
                        break

                    # 2. Poll RAG Status File (if exists)
                    if os.path.exists(rag_status_file):
                        try:
                            with open(rag_status_file, "r") as f:
                                status_data = json.load(f)

                            current = status_data.get("current", 0)
                            total = status_data.get("total", 1)
                            fname = status_data.get("last_file", "...")

                            # Update Progress Bar
                            if total > 0:
                                progress = min(current / total, 1.0)
                                rag_progress_bar.progress(
                                    progress,
                                    text=_["rag_progress"].format(current=current, total=total, fname=fname)
                                )
                        except Exception:
                            pass  # Ignore read errors during race conditions

                    time.sleep(0.2) # Yield to allow thread to work

                # Cleanup status file if left over
                if os.path.exists(rag_status_file):
                    try:
                        os.remove(rag_status_file)
                    except Exception:
                        pass

                st.session_state.agent_state = final_state

                # Guardar resultados en session_state para persistencia
                if os.path.exists("reports/reporte_final.html"):
                    with open("reports/reporte_final.html", "r", encoding="utf-8") as f:
                        st.session_state.report_html = f.read()

                st.session_state.last_topic = topic
                st.session_state.investigation_done = True

                status.update(label=_["status_done"], state="complete", expanded=False)
                st.balloons()

            except Exception as e:
                st.error(_["error_msg"].format(e=e))
                status.update(label=_["status_error"], state="error")

# --- SECCIÓN DE RESULTADOS ---
if st.session_state.investigation_done:
    st.divider()
    _topic = _["autoreport_topic"] if st.session_state.last_topic == "__saved_report__" else st.session_state.last_topic
    st.subheader(_["results_header"].format(topic=_topic))

    # Multi-format Download Center
    st.write(_["downloads_header"])
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if os.path.exists("reports/reporte_investigacion.pdf"):
            with open("reports/reporte_investigacion.pdf", "rb") as f:
                st.download_button("📕 PDF", f, "reporte.pdf", "application/pdf")

    with col2:
        if os.path.exists("reports/reporte_final.docx"):
            with open("reports/reporte_final.docx", "rb") as f:
                st.download_button("📘 Word", f, "reporte.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with col3:
        if os.path.exists("reports/reporte_final.md"):
            with open("reports/reporte_final.md", "rb") as f:
                st.download_button("📝 Markdown", f, "reporte.md", "text/markdown")

    with col4:
        if os.path.exists("reports/reporte_final.html"):
            with open("reports/reporte_final.html", "rb") as f:
                st.download_button("🌐 HTML", f, "reporte.html", "text/html")

    # Mostrar el reporte HTML persistido
    if st.session_state.report_html:
        with st.expander(_["report_expander"], expanded=False):
            components.html(st.session_state.report_html, height=800, scrolling=True)

    # --- EXPLORADOR DE FUENTES (Source Explorer) ---
    st.divider()
    st.subheader(_["sources_header"])

    if st.session_state.agent_state:
        state = st.session_state.agent_state
        sources_list = []

        # Collect all sources with content
        for key in ["wiki_research", "web_research", "arxiv_research", "scholar_research", "github_research", "reddit_research", "local_research"]:
            if state.get(key):
                for item in state[key]:
                    sources_list.append({
                        "type": key.split("_")[0].upper(),
                        "title": item.get("title") or item.get("name") or _["source_untitled"],
                        "content": item.get("content") or item.get("summary") or item.get("description") or _["source_no_content"],
                        "url": item.get("url")
                    })

        if sources_list:
            selected_source_idx = st.selectbox(
                _["sources_select"],
                range(len(sources_list)),
                format_func=lambda x: f"[{sources_list[x]['type']}] {sources_list[x]['title']}"
            )

            src = sources_list[selected_source_idx]
            st.info(_["source_label"].format(type=src['type'], title=src['title']))
            st.markdown(src['content'])
            if src['url']:
                st.link_button(_["source_open_btn"], src['url'])
        else:
            st.info(_["sources_empty"])

    # --- CHAT INTERACTIVO ---
    st.divider()
    st.subheader(_["chat_header"])

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input(_["chat_input"]):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(_["chat_thinking"]):
                from langchain_core.messages import HumanMessage, AIMessage

                # Prepare state for the agent
                current_state = st.session_state.agent_state or {"topic": st.session_state.last_topic, "messages": []}

                # Convert session state messages to LangChain objects
                lc_messages = []
                for m in st.session_state.messages[:-1]: # All except the last one which is already added
                     if m["role"] == "user":
                         lc_messages.append(HumanMessage(content=m["content"]))
                     else:
                         lc_messages.append(AIMessage(content=m["content"]))

                current_state["messages"] = lc_messages + [HumanMessage(content=prompt)]

                try:
                    from src.tools.chat_tools import chat_node
                    response_state = chat_node(current_state)
                    ai_response = response_state["messages"][0].content

                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})

                    # Update persisted agent state
                    current_state["messages"].append(AIMessage(content=ai_response))
                    st.session_state.agent_state = current_state

                except Exception as e:
                    st.error(_["chat_error"].format(e=e))

# Footer
st.divider()
st.markdown(f"""
    <div style='text-align: center' class='status-text'>
        Research-Agent v1.0.1 | DB: {os.environ.get('DB_PATH', 'Default')} | PWD: {os.getcwd()}
    </div>
    """, unsafe_allow_html=True)


def main():
    """Entry point for research-agent-ui CLI command."""
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__, "--server.address=0.0.0.0"])
