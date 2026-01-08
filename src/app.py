import streamlit as st
import os
import subprocess
import time
from agent import app
import streamlit.components.v1 as components

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
        ["qwen2.5:14b", "gemma3:12b", "llama3:8b"],
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
        with st.status("🚀 Procesando investigación...", expanded=True) as status:
            try:
                # Actualizar variables de entorno para el modelo seleccionado
                os.environ["OLLAMA_MODEL"] = llm_model
                
                # Pass selected sources to the agent if any are selected
                inputs = {"topic": topic}
                if selected_sources:
                    inputs["research_plan"] = selected_sources
                    # If user manually selected sources, we skip the planning node's logic
                    # and go straight to the first selected node
                    inputs["next_node"] = selected_sources[0]
                
                st.write(f"🧠 Analizando fuentes para: **{topic}**...")
                
                # Ejecución del agente
                final_state = app.invoke(inputs)
                
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
    
    # Botón de Descarga PDF (con corrección de lectura de datos)
    if os.path.exists("reporte_investigacion.pdf"):
        with open("reporte_investigacion.pdf", "rb") as f:
            pdf_bytes = f.read()
            st.download_button(
                label="📥 Descargar Reporte (PDF)",
                data=pdf_bytes,
                file_name=f"reporte_{st.session_state.last_topic.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="download_pdf_btn"
            )
    
    # Mostrar el reporte HTML persistido
    if st.session_state.report_html:
        with st.expander("📄 Ver Reporte Completo", expanded=False):
            components.html(st.session_state.report_html, height=800, scrolling=True)

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
