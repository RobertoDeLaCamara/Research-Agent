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
    
    st.divider()
    st.write("### Fuentes Activas")
    st.checkbox("Wikipedia", value=True, disabled=True)
    st.checkbox("Web Search (Tavily)", value=True, disabled=True)
    st.checkbox("arXiv", value=True, disabled=True)
    st.checkbox("Semantic Scholar", value=True, disabled=True)
    st.checkbox("GitHub", value=True, disabled=True)
    st.checkbox("Hacker News", value=True, disabled=True)
    st.checkbox("Stack Overflow", value=True, disabled=True)
    st.checkbox("YouTube Summaries", value=True, disabled=True)

# --- Inicialización de Session State ---
if "investigation_done" not in st.session_state:
    st.session_state.investigation_done = False
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""
if "report_html" not in st.session_state:
    st.session_state.report_html = ""

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
                
                inputs = {"topic": topic}
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
        components.html(st.session_state.report_html, height=1000, scrolling=True)

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center' class='status-text'>
        Research-Agent v1.0.0 | Desarrollado con LangGraph & Streamlit
    </div>
    """, unsafe_allow_html=True)
