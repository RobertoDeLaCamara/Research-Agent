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
    hn_research: List[dict]
    so_research: List[dict]
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
    # Premium HTML Design with modern CSS
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Informe: {topic}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                box-sizing: border-box;
            }}

            :root {{
                --primary: #2563eb;
                --primary-dark: #1e40af;
                --secondary: #64748b;
                --bg: #f8fafc;
                --card-bg: #ffffff;
                --text: #1e293b;
                --text-light: #64748b;
                --accent: #eff6ff;
                --border: #e2e8f0;
            }}
            
            body {{ 
                font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                line-height: 1.6; 
                color: var(--text); 
                background-color: var(--bg);
                margin: 0;
                padding: 0;
            }}
            
            .container {{
                max-width: 900px;
                margin: 40px auto;
                padding: 0 20px;
            }}
            
            header {{
                text-align: center;
                margin-bottom: 50px;
                padding: 40px 0;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                color: white;
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            }}
            
            h1 {{ margin: 0; font-weight: 700; font-size: 2.5rem; letter-spacing: -0.025em; }}
            .subtitle {{ opacity: 0.8; font-weight: 300; margin-top: 10px; font-size: 1.1rem; }}
            
            h2 {{ 
                color: var(--text); 
                font-size: 1.75rem; 
                margin-top: 40px; 
                margin-bottom: 20px;
                border-left: 4px solid var(--primary);
                padding-left: 15px;
            }}
            
            .section-card {{
                background: var(--card-bg);
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                margin-bottom: 30px;
                border: 1px solid var(--border);
            }}
            
            .synthesis-card {{
                background: linear-gradient(to bottom right, #eff6ff, #ffffff);
                border: 1px solid #bfdbfe;
                padding: 40px;
            }}
            
            .synthesis-card h2 {{ border-left-color: #3b82f6; margin-top: 0; }}
            
            .research-item {{
                margin-bottom: 25px;
                padding-bottom: 20px;
                border-bottom: 1px solid var(--border);
            }}
            
            .research-item:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
            
            .item-title {{ font-weight: 600; font-size: 1.25rem; color: var(--primary); margin-bottom: 8px; display: block; }}
            .item-meta {{ font-size: 0.875rem; color: var(--text-light); margin-bottom: 12px; }}
            .item-content {{ 
                font-size: 1rem; 
                color: var(--text); 
                word-break: break-word;
            }}
            
            a {{ color: var(--primary); text-decoration: none; font-weight: 500; }}
            a:hover {{ color: var(--primary-dark); text-decoration: underline; }}
            
            .tag {{
                display: inline-block;
                padding: 2px 10px;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                background: var(--accent);
                color: var(--primary);
                margin-bottom: 10px;
            }}
            
            .summary-text {{ 
                white-space: pre-wrap; 
                word-break: break-word;
            }}
            
            .bib-list {{ list-style: none; padding: 0; }}
            .bib-list li {{ 
                padding: 12px 0; 
                border-bottom: 1px solid var(--border);
                font-size: 0.95rem;
                word-break: break-all;
            }}
            
            @media (max-width: 640px) {{
                h1 {{ font-size: 1.75rem; }}
                .container {{ margin: 20px auto; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Investigación Inteligente</h1>
                <div class="subtitle">{topic}</div>
            </header>
    """

    # --- SECCIÓN: SÍNTESIS EJECUTIVA ---
    if state.get("consolidated_summary"):
        synthesis_html = markdown.markdown(state["consolidated_summary"])
        html_content += f"""
        <div class="section-card synthesis-card">
            <h2>💡 Síntesis Ejecutiva Consolidada</h2>
            <div class="summary-text">{synthesis_html}</div>
        </div>
        """

    # --- SECCIÓN: WIKIPEDIA ---
    if state.get("wiki_research"):
        html_content += "<h2><span class='tag'>WIKIPEDIA</span> Contexto General</h2><div class='section-card'>"
        for item in state["wiki_research"]:
            summary = item.get('summary', '')
            if len(summary) > 500:
                summary = summary[:500] + "..."
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url')}" class="item-title">{item.get('title')}</a>
                <p class="item-content">{summary}</p>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: WEB RESEARCH ---
    if state.get("web_research"):
        html_content += "<h2><span class='tag'>WEB</span> Investigación Ampliada</h2><div class='section-card'>"
        for item in state["web_research"]:
            content = item.get('content', item.get('snippet', ''))
            if len(content) > 500:
                content = content[:500] + "..."
            html_content += f"""
            <div class="research-item">
                <p class="item-content">{content}</p>
                <a href="{item.get('url')}" class="item-meta">Ver fuente original &rarr;</a>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: ARXIV ---
    if state.get("arxiv_research"):
        html_content += "<h2><span class='tag'>ACADÉMICO</span> Artículos en arXiv</h2><div class='section-card'>"
        for item in state["arxiv_research"]:
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url', '#')}" class="item-title">{item.get('title')}</a>
                <div class="item-meta">Autores: {item.get('authors')}</div>
                <p class="item-content">{item.get('summary')}</p>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: SEMANTIC SCHOLAR ---
    if state.get("scholar_research"):
        html_content += "<h2><span class='tag'>CIENCIA</span> Semantic Scholar</h2><div class='section-card'>"
        for item in state["scholar_research"]:
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url', '#')}" class="item-title">{item.get('title')} ({item.get('year', 'N/A')})</a>
                <div class="item-meta">Autores: {item.get('authors')}</div>
                <p class="item-content">{item.get('content')}</p>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: GITHUB ---
    if state.get("github_research"):
        html_content += "<h2><span class='tag'>CÓDIGO</span> Repositorios Destacados</h2><div class='section-card'>"
        for item in state["github_research"]:
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url')}" class="item-title">{item.get('name')} (⭐ {item.get('stars')})</a>
                <p class="item-content">{item.get('description')}</p>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: HACKER NEWS ---
    if state.get("hn_research"):
        html_content += "<h2><span class='tag'>HACKER NEWS</span> Discusiones</h2><div class='section-card'>"
        for item in state["hn_research"]:
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url')}" class="item-title">{item.get('title')}</a>
                <div class="item-meta">Autor: {item.get('author')} | Puntos: {item.get('points')}</div>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: STACK OVERFLOW ---
    if state.get("so_research"):
        html_content += "<h2><span class='tag'>STACK OVERFLOW</span> Soporte Técnico</h2><div class='section-card'>"
        for item in state["so_research"]:
            html_content += f"""
            <div class="research-item">
                <a href="{item.get('url')}" class="item-title">{item.get('title')}</a>
                <div class="item-meta">Score: {item.get('score')} | Resuelta: {'Sí' if item.get('is_answered') else 'No'}</div>
                <div class="tag-container">
                    {' '.join([f'<span class="tag">{t.strip()}</span>' for t in item.get('tags', '').split(',')])}
                </div>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: YOUTUBE ---
    if summaries:
        html_content += "<h2><span class='tag'>MULTIMEDIA</span> Análisis de YouTube</h2><div class='section-card'>"
        for i, (summary, metadata) in enumerate(zip(summaries, video_metadata)):
            html_content += f"""
            <div class="research-item">
                <div class="item-title">Vídeo {i+1}: {metadata.get('title', 'Sin título')}</div>
                <div class="item-meta">Autor: {metadata.get('author', 'Desconocido')} | <a href="{metadata.get('url', '#')}">Ver en YouTube</a></div>
                <div class="item-content summary-text">{summary}</div>
            </div>
            """
        html_content += "</div>"

    # --- SECCIÓN: BIBLIOGRAFÍA ---
    bibliography = []
    html_content += "<hr><h2>📚 Bibliografía y Fuentes</h2><div class='section-card'><ul class='bib-list'>"
    
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
    # Hacker News
    for item in state.get("hn_research", []):
        url = item.get('url', '#')
        title = item.get('title', 'Hacker News')
        ref = f"Hacker News: {title} - {url}"
        bibliography.append(ref)
        html_content += f"<li>Hacker News: {title} - <a href='{url}'>{url}</a></li>"
    # Stack Overflow
    for item in state.get("so_research", []):
        url = item.get('url', '#')
        title = item.get('title', 'Stack Overflow')
        ref = f"Stack Overflow: {title} - {url}"
        bibliography.append(ref)
        html_content += f"<li>Stack Overflow: {title} - <a href='{url}'>{url}</a></li>"
    # YouTube
    for metadata in video_metadata:
        url = metadata.get('url', '#')
        title = metadata.get('title', 'Video')
        author = metadata.get('author', 'Autor')
        ref = f"YouTube: {title} por {author} - {url}"
        bibliography.append(ref)
        html_content += f"<li>YouTube: {title} por {author} - <a href='{url}'>{url}</a></li>"
    
    html_content += "</ul></div>"

    html_content += """
    </div>
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