# src/tools/reporting_tools.py

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import markdown
from fpdf import FPDF

# Importamos la definición de AgentState desde el archivo agent.py
from typing import TypedDict, List
from langchain_core.messages import BaseMessage

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
    messages: List[BaseMessage]

# --------------------------------------------------------------------------
# NODO 3: GENERACIÓN DEL INFORME EN HTML
# --------------------------------------------------------------------------
def generate_report_node(state: AgentState) -> dict:
    """
    Toma los resúmenes y metadatos del estado para crear un informe completo en formato HTML.

    Args:
        state (AgentState): El estado actual del agente, que debe contener
                            'summaries', 'video_metadata' y 'topic'.

    Returns:
        dict: Un diccionario con la clave 'report' para actualizar el estado del agente.
    """
    print("\n--- 📄 NODO: GENERANDO INFORME ---")
    summaries = state["summaries"]
    video_metadata = state["video_metadata"]
    topic = state["topic"]

    if not summaries:
        print("⚠️ No hay resúmenes para generar un informe.")
        report_html = f"<h1>Informe de Investigación sobre: {topic}</h1><p>No se encontraron vídeos o no se pudieron procesar.</p>"
        return {"report": report_html}

    # Usamos f-strings de varias líneas para construir el HTML de manera legible.
    # Se añade un poco de estilo CSS en línea para mejorar la apariencia.
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            h1 {{ color: #444; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
            h2 {{ color: #555; }}
            h3 {{ color: #666; }}
            a {{ color: #1a0dab; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .video-block {{ margin-bottom: 30px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #f9f9f9; }}
            .summary {{ white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <h1>Informe de Investigación sobre: {topic}</h1>
    """

    # --- SECCIÓN: RESUMEN CONSOLIDADO (SÍNTESIS) ---
    if state.get("consolidated_summary"):
        # Convertimos el markdown de la síntesis a HTML para el informe
        synthesis_html = markdown.markdown(state["consolidated_summary"])
        html_content += f"""
        <div style="background-color: #eefbff; padding: 20px; border-radius: 10px; border: 1px solid #b3e5fc; margin-bottom: 30px;">
            <h1 style="color: #01579b; border: none;">💡 Síntesis Ejecutiva Consolidada</h1>
            <div class="summary">{synthesis_html}</div>
        </div>
        <hr style="border: 1px solid #ddd; margin: 40px 0;">
        """

    # --- SECCIÓN: WIKIPEDIA ---
    if state.get("wiki_research"):
        html_content += "<h1>Contexto General (Wikipedia)</h1>"
        for item in state["wiki_research"]:
            summary = item.get('summary', '')
            if len(summary) > 500:
                summary = summary[:500] + "..."
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('title')}</h2>
                <p>{summary}</p>
                <p><a href="{item.get('url')}">Leer más en Wikipedia</a></p>
            </div>
            """

    # --- SECCIÓN: WEB RESEARCH ---
    if state.get("web_research"):
        html_content += "<h1>Investigación Web</h1>"
        for item in state["web_research"]:
            content = item.get('content', item.get('snippet', ''))
            if len(content) > 500:
                content = content[:500] + "..."
            html_content += f"""
            <div class="video-block">
                <p>{content}</p>
                <p><a href="{item.get('url')}">Fuente original</a></p>
            </div>
            """

    # --- SECCIÓN: ARXIV ---
    if state.get("arxiv_research"):
        html_content += "<h1>Artículos Científicos (arXiv)</h1>"
        for item in state["arxiv_research"]:
            url = item.get('url', '#')
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('title')}</h2>
                <p><strong>Autores:</strong> {item.get('authors')}</p>
                <p>{item.get('summary')}</p>
                <p><a href="{url}">Ver en arXiv</a></p>
            </div>
            """

    # --- SECCIÓN: SEMANTIC SCHOLAR ---
    if state.get("scholar_research"):
        html_content += "<h1>Artículos Destacados (Semantic Scholar)</h1>"
        for item in state["scholar_research"]:
            url = item.get('url', '#')
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('title')} ({item.get('year', 'N/A')})</h2>
                <p><strong>Autores:</strong> {item.get('authors')}</p>
                <p>{item.get('content')}</p>
                <p><a href="{url}">Ver en Semantic Scholar</a></p>
            </div>
            """

    # --- SECCIÓN: GITHUB ---
    if state.get("github_research"):
        html_content += "<h1>Repositorios de Código (GitHub)</h1>"
        for item in state["github_research"]:
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('name')} (⭐ {item.get('stars')})</h2>
                <p>{item.get('description')}</p>
                <p><a href="{item.get('url')}">Ver en GitHub</a></p>
            </div>
            """

    html_content += "<h1>Investigación de YouTube</h1>"
    for i, (summary, metadata) in enumerate(zip(summaries, video_metadata)):
        html_content += f"""
        <div class="video-block">
            <h2>Vídeo {i+1}: {metadata.get('title', 'Título no disponible')}</h2>
            <p><strong>Autor:</strong> {metadata.get('author', 'Autor no disponible')}</p>
            <p><strong>URL:</strong> <a href="{metadata.get('url', '#')}">{metadata.get('url', 'URL no disponible')}</a></p>
            <h3>Resumen Ejecutivo:</h3>
            <p class="summary">{summary}</p>
        </div>
        """

    # --- SECCIÓN: BIBLIOGRAFÍA ---
    bibliography = []
    html_content += "<hr><h1>Bibliografía y Fuentes</h1><ul>"
    
    # Wiki
    for item in state.get("wiki_research", []):
        url = item.get('url', '#')
        title = item.get('title', 'Wikipedia')
        ref = f"Wikipedia: {title} - {url}"
        bibliography.append(ref)
        html_content += f"<li>Wikipedia: {title} - <a href='{url}'>{url}</a></li>"
    # arXiv
    for item in state.get("arxiv_research", []):
        url = item.get('url', '#')
        title = item.get('title', 'Articulo arXiv')
        authors = item.get('authors', 'Desconocido')
        ref = f"arXiv: {title} ({authors}) - {url}"
        bibliography.append(ref)
        html_content += f"<li>arXiv: {title} ({authors}) - <a href='{url}'>{url}</a></li>"
    # Scholar
    for item in state.get("scholar_research", []):
        url = item.get('url', '#')
        title = item.get('title', 'Articulo Scholar')
        year = item.get('year', 'N/A')
        ref = f"Semantic Scholar: {title} ({year}) - {url}"
        bibliography.append(ref)
        html_content += f"<li>Semantic Scholar: {title} ({year}) - <a href='{url}'>{url}</a></li>"
    # GitHub
    for item in state.get("github_research", []):
        url = item.get('url', '#')
        name = item.get('name', 'Repository')
        ref = f"GitHub: {name} - {url}"
        bibliography.append(ref)
        html_content += f"<li>GitHub: {name} - <a href='{url}'>{url}</a></li>"
    # YouTube
    for metadata in video_metadata:
        url = metadata.get('url', '#')
        title = metadata.get('title', 'Video')
        author = metadata.get('author', 'Autor')
        ref = f"YouTube: {title} por {author} - {url}"
        bibliography.append(ref)
        html_content += f"<li>YouTube: {title} por {author} - <a href='{url}'>{url}</a></li>"
    
    html_content += "</ul>"

    html_content += """
    </body>
    </html>
    """
    
    # Guardamos el HTML
    report_path = "reporte_final.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # --- GENERACIÓN DE PDF ---
    pdf_path = "reporte_investigacion.pdf"
    try:
        generate_pdf(state, topic, pdf_path, bibliography) # <--- Pasamos la bibliografía local
        print("✅ PDF generado con éxito.")
    except Exception as e:
        print(f"⚠️ Error al generar PDF: {e}")
        pdf_path = None

    print("✅ Informe HTML generado con éxito.")
    return {"report": html_content, "bibliography": bibliography, "pdf_path": pdf_path}

def generate_pdf(state: AgentState, topic: str, output_path: str, bibliography_list: list = None):
    """Genera un archivo PDF profesional usando fpdf2 con todas las secciones."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Margen explícito
    l_margin = 15
    pdf.set_left_margin(l_margin)
    pdf.set_right_margin(l_margin)
    eff_w = pdf.w - 2 * l_margin

    # Usamos Helvetica (estándar). No admite emojis ni caracteres especiales complejos.
    pdf.set_font("Helvetica", "B", 16)
    
    # Título
    safe_topic = topic.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(eff_w, 10, f"Informe de Investigacion: {safe_topic}", align='C')
    pdf.ln(5)
    
    def clean_text(text):
        if not text: return ""
        # Removemos acentos problemáticos y emojis
        import unicodedata
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return text

    def add_section_header(title):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_fill_color(230, 230, 230)
        pdf.multi_cell(eff_w, 10, clean_text(title), fill=True)
        pdf.ln(2)

    # Síntesis
    add_section_header("Sintesis Ejecutiva Consolidada")
    pdf.set_font("Helvetica", "", 10)
    summary_text = state.get("consolidated_summary", "No disponible").replace("#", "").replace("*", "")
    pdf.multi_cell(eff_w, 6, clean_text(summary_text))
    pdf.ln(5)


    pdf.output(output_path)


# --------------------------------------------------------------------------
# NODO 4: ENVÍO DEL INFORME POR CORREO ELECTRÓNICO
# --------------------------------------------------------------------------
def send_email_node(state: AgentState) -> dict:
    """
    Envía el informe generado por correo electrónico utilizando las credenciales del archivo .env.

    Args:
        state (AgentState): El estado actual del agente, que contiene el 'report' en HTML.

    Returns:
        dict: Un diccionario vacío, ya que este es un nodo final que no modifica el estado.
    """
    print("\n--- 📧 NODO: ENVIANDO CORREO ELECTRÓNICO ---")
    report = state["report"]
    topic = state["topic"]

    # Obtenemos la configuración del correo desde las variables de entorno.
    sender_email = os.getenv("EMAIL_USERNAME")
    receiver_email = os.getenv("EMAIL_RECIPIENT")
    password = os.getenv("EMAIL_PASSWORD")
    host = os.getenv("EMAIL_HOST", "smtp.gmail.com") # Valor por defecto para Gmail
    port = int(os.getenv("EMAIL_PORT", 587))         # Puerto estándar

    if not all([sender_email, receiver_email, password]):
        print("❌ Faltan credenciales de correo en el archivo .env. No se puede enviar el correo.")
        return {}

    # Creación del objeto del mensaje de correo.
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"Informe de Investigación: {topic}"
    msg.attach(MIMEText(state["report"], 'html'))

    # Adjuntamos el PDF si existe
    pdf_path = state.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(pdf_path)}",
            )
            msg.attach(part)
            print(f"✅ PDF adjunto al correo: {pdf_path}")
        except Exception as e:
            print(f"⚠️ Error al adjuntar PDF: {e}")

    try:
        # Iniciamos la conexión con el servidor SMTP.
        print(f"Conectando al servidor SMTP en {host}:{port}...")
        server = smtplib.SMTP(host, port)
        server.starttls()  # Habilitamos la seguridad (cifrado)
        server.login(sender_email, password)
        
        # Enviamos el correo.
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print(f"✅ Correo electrónico enviado con éxito a {receiver_email}.")
        
    except smtplib.SMTPAuthenticationError:
        print("❌ Error de autenticación. Revisa tu EMAIL_USERNAME y EMAIL_PASSWORD.")
        print("   Recuerda que para Gmail, necesitas una 'Contraseña de Aplicación'.")
    except Exception as e:
        print(f"❌ Error al enviar el correo: {e}")
    finally:
        if 'server' in locals() and server.sock:
            server.quit() # Cerramos la conexión con el servidor.

    # Este nodo no necesita devolver nada para actualizar el estado,
    # ya que es el último paso del proceso.
    return {}