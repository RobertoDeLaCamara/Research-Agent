import streamlit as st
import os
import subprocess
import time
from agent import app
import streamlit.components.v1 as components
from db_manager import get_recent_sessions, load_session, clear_history

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

# Sidebar
with st.sidebar:
    st.title("⚙️ Configuración")
    st.info("Configura los parámetros de tu investigación.")
    
    llm_model = st.selectbox(
        "Modelo LLM (Ollama)",
        ["qwen3:14b", "qwen2.5:14b", "gemma3:12b", "llama3:8b"],
        index=0
    )
    
    st.write("### Fuentes Activas")
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
    
    st.write("### 📏 Profundidad")
    depth_mode = st.radio(
        "Modo de investigación:",
        ["Rápido", "Estándar", "Profundo"],
        index=1,
        help="Afecta al número de resultados y a la exhaustividad del análisis."
    )
    
    depth_mapping = {
        "Rápido": "quick",
        "Estándar": "standard",
        "Profundo": "deep"
    }
    research_depth = depth_mapping[depth_mode]

    st.write("### 🧠 Perfil de Investigador")
    persona_mode = st.selectbox(
        "Persona del agente:",
        ["Generalista", "Analista de Mercado", "Arquitecto de Software", "Revisor Científico", "Product Manager", "Editor de Noticias"],
        index=0,
        help="Ajusta el tono de la síntesis y la prioridad de las fuentes."
    )
    
    persona_mapping = {
        "Generalista": "general",
        "Analista de Mercado": "business",
        "Arquitecto de Software": "tech",
        "Revisor Científico": "academic",
        "Product Manager": "pm",
        "Editor de Noticias": "news_editor"
    }
    persona = persona_mapping[persona_mode]

    st.write("### ⏱️ Filtro Temporal")
    last_24h = st.checkbox("Filtrar por últimas 24h", value=False, help="Solo para web y Reddit. Útil para noticias de última hora.")
    time_range = "d" if last_24h else None

    st.write("### 📁 Conocimiento Local")
    use_rag = st.checkbox("Incluir base de conocimientos local", value=False, help="Busca en archivos locales (.pdf, .txt) en ./knowledge_base")
    
    uploaded_files = st.file_uploader("Subir archivos para investigar", type=["pdf", "txt"], accept_multiple_files=True)
    if uploaded_files:
        kb_path = "./knowledge_base"
        if not os.path.exists(kb_path):
            os.makedirs(kb_path)
        for uploaded_file in uploaded_files:
            with open(os.path.join(kb_path, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"✅ {len(uploaded_files)} archivos listos.")

    st.divider()
    st.write("### 📂 Historial")
    recent_sessions = get_recent_sessions(limit=10)
    if recent_sessions:
        session_options = ["Seleccionar..."] + [f"{s[3][:16]} | {s[1]}" for s in recent_sessions]
        selected_session_label = st.selectbox("Cargar investigación previa:", session_options)
        
        if selected_session_label != "Seleccionar...":
            if st.button("📂 Cargar Sesión"):
                session_idx = session_options.index(selected_session_label) - 1
                session_id = recent_sessions[session_idx][0]
                loaded_state = load_session(session_id)
                if loaded_state:
                    st.session_state.agent_state = loaded_state
                    st.session_state.last_topic = loaded_state.get("topic", "Cargado")
                    # Map 'report' from state to 'report_html' for UI
                    st.session_state.report_html = loaded_state.get("report", "")
                    st.session_state.investigation_done = True
                    st.success(f"Cargado: {st.session_state.last_topic}")
                    st.rerun()
    else:
        st.write("No hay sesiones previas.")
        
    if st.button("🗑️ Limpiar Historial", type="secondary", use_container_width=True):
        if clear_history():
            st.success("Historial borrado correctamente.")
            st.rerun()

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

# Auto-detectar reportes existentes al iniciar
if not st.session_state.investigation_done:
    if os.path.exists("reporte_final.html"):
        with open("reporte_final.html", "r", encoding="utf-8") as f:
            st.session_state.report_html = f.read()
        st.session_state.investigation_done = True
        st.session_state.last_topic = "Reporte Guardado"

# Main UI
st.title("🔍 Research-Agent")
st.subheader("Tu asistente inteligente de investigación multimodal")

topic = st.text_input("¿Qué quieres investigar hoy?", placeholder="Ej. Explainable AI, Docker Orchestration...")

if st.button("Iniciar Investigación"):
    if not topic:
        st.warning("Por favor, introduce un tema.")
    else:
        # Clear previous state to ensure clean start
        st.session_state.investigation_done = False
        st.session_state.report_html = ""
        st.session_state.agent_state = None
        
        with st.status("🚀 Procesando investigación...", expanded=True) as status:
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
                
                # Use a dict for node description mappings
                node_messages = {
                    "initialize_state": "⚙️ Inicializando estado...",
                    "plan_research": "🗺️ Planificando estrategia de búsqueda...",
                    "search_videos": "📺 Buscando vídeos en YouTube...",
                    "summarize_videos": "📝 Resumiendo contenido audiovisual...",
                    "search_web": "🌐 Explorando la web...",
                    "search_wiki": "📚 Consultando Wikipedia...",
                    "search_arxiv": "🎓 Buscando artículos en arXiv...",
                    "search_scholar": "🔬 Investigando en Semantic Scholar...",
                    "search_github": "💻 Explorando repositorios en GitHub...",
                    "search_hn": "🧡 Buscando discusiones en Hacker News...",
                    "search_so": "💙 Consultando Stack Overflow...",
                    "search_reddit": "🤖 Analizando opiniones en Reddit...",
                    "local_rag": "📁 Analizando conocimiento local (RAG)...",
                    "consolidate_research": "🧠 Sintetizando toda la información...",
                    "evaluate_research": "⚖️ Evaluando calidad y buscando vacíos...",
                    "generate_report": "📄 Generando informe final...",
                    "send_email": "📧 Enviando reporte por correo..."
                }

                # Streaming execution to show progress (Improved Reactive Logic)
                final_state = inputs.copy()
                
                # Container to keep track of the current status message
                status_container = st.empty()
                
                for chunk in app.stream(inputs, config={"recursion_limit": 100}):
                    for node_name, state_update in chunk.items():
                        # Aggregately update final_state (defensive check)
                        if isinstance(state_update, dict):
                            final_state.update(state_update)
                        
                        # Mark current node as COMPLETED
                        completed_msg = node_messages.get(node_name, f"Ejecutando {node_name}...")
                        st.write(f"✅ {completed_msg}")
                        
                        # Guess the NEXT node from state_update or original plan
                        next_node = state_update.get("next_node")
                        if next_node and next_node != "END":
                            next_msg = node_messages.get(next_node, f"Iniciando {next_node}...")
                            status_container.info(f"⏳ {next_msg}")
                        else:
                            status_container.empty()
                
                st.session_state.agent_state = final_state
                
                # Guardar resultados en session_state para persistencia
                if os.path.exists("reporte_final.html"):
                    with open("reporte_final.html", "r", encoding="utf-8") as f:
                        st.session_state.report_html = f.read()
                
                st.session_state.last_topic = topic
                st.session_state.investigation_done = True
                
                status.update(label="✅ ¡Investigación Completada!", state="complete", expanded=False)
                st.balloons()
                
            except Exception as e:
                st.error(f"Ocurrió un error durante la investigación: {e}")
                status.update(label="❌ Error en la investigación", state="error")

# --- SECCIÓN DE RESULTADOS ---
if st.session_state.investigation_done:
    st.divider()
    st.subheader(f"📄 Resultado: {st.session_state.last_topic}")
    
    # Multi-format Download Center
    st.write("### 📥 Centro de Descargas")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if os.path.exists("reporte_investigacion.pdf"):
            with open("reporte_investigacion.pdf", "rb") as f:
                st.download_button("📕 PDF", f, "reporte.pdf", "application/pdf")
    
    with col2:
        if os.path.exists("reporte_final.docx"):
            with open("reporte_final.docx", "rb") as f:
                st.download_button("📘 Word", f, "reporte.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                
    with col3:
        if os.path.exists("reporte_final.md"):
            with open("reporte_final.md", "rb") as f:
                st.download_button("📝 Markdown", f, "reporte.md", "text/markdown")
                
    with col4:
        if os.path.exists("reporte_final.html"):
            with open("reporte_final.html", "rb") as f:
                st.download_button("🌐 HTML", f, "reporte.html", "text/html")
    
    # Mostrar el reporte HTML persistido
    if st.session_state.report_html:
        with st.expander("📄 Ver Reporte Completo", expanded=False):
            components.html(st.session_state.report_html, height=800, scrolling=True)

    # --- EXPLORADOR DE FUENTES (Source Explorer) ---
    st.divider()
    st.subheader("🔍 Explorador de Fuentes")
    
    if st.session_state.agent_state:
        state = st.session_state.agent_state
        sources_list = []
        
        # Collect all sources with content
        for key in ["wiki_research", "web_research", "arxiv_research", "scholar_research", "github_research", "reddit_research", "local_research"]:
            if state.get(key):
                for item in state[key]:
                    sources_list.append({
                        "type": key.split("_")[0].upper(),
                        "title": item.get("title") or item.get("name") or "Sin título",
                        "content": item.get("content") or item.get("summary") or item.get("description") or "Sin contenido",
                        "url": item.get("url")
                    })
                    
        if sources_list:
            selected_source_idx = st.selectbox("Selecciona una fuente para explorar el fragmento original:", 
                                             range(len(sources_list)), 
                                             format_func=lambda x: f"[{sources_list[x]['type']}] {sources_list[x]['title']}")
            
            src = sources_list[selected_source_idx]
            st.info(f"**Fuente:** [{src['type']}] {src['title']}")
            st.markdown(src['content'])
            if src['url']:
                st.link_button("🔗 Abrir fuente original", src['url'])
        else:
            st.info("No hay fuentes detalladas disponibles para este reporte.")

    # --- CHAT INTERACTIVO ---
    st.divider()
    st.subheader("💬 Chat con tu Investigador")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Pregúntame sobre la investigación..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
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
                
                # In a real LangGraph flow, we might want to invoke a specific part of the graph
                # For now, we'll implement a direct chat response or a specific chat branch
                try:
                    # Use the chat_node directly if we just want conversation
                    from tools.chat_tools import chat_node
                    response_state = chat_node(current_state)
                    ai_response = response_state["messages"][0].content
                    
                    st.markdown(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                    
                    # Update persisted agent state
                    current_state["messages"].append(AIMessage(content=ai_response))
                    st.session_state.agent_state = current_state
                    
                except Exception as e:
                    st.error(f"Error en el chat: {e}")

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center' class='status-text'>
        Research-Agent v1.0.0 | Desarrollado con LangGraph & Streamlit
    </div>
    """, unsafe_allow_html=True)
