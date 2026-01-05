# src/tools/reporting_tools.py

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    consolidated_summary: str
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
        import markdown
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
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('title')}</h2>
                <p>{item.get('summary')}</p>
                <p><a href="{item.get('url')}">Leer más en Wikipedia</a></p>
            </div>
            """

    # --- SECCIÓN: WEB RESEARCH ---
    if state.get("web_research"):
        html_content += "<h1>Investigación Web</h1>"
        for item in state["web_research"]:
            html_content += f"""
            <div class="video-block">
                <p>{item.get('content', item.get('snippet', ''))}</p>
                <p><a href="{item.get('url')}">Fuente original</a></p>
            </div>
            """

    # --- SECCIÓN: ARXIV ---
    if state.get("arxiv_research"):
        html_content += "<h1>Artículos Científicos (arXiv)</h1>"
        for item in state["arxiv_research"]:
            html_content += f"""
            <div class="video-block">
                <h2>{item.get('title')}</h2>
                <p><strong>Autores:</strong> {item.get('authors')}</p>
                <p>{item.get('summary')}</p>
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

    html_content += """
    </body>
    </html>
    """

    print("✅ Informe HTML generado con éxito.")
    return {"report": html_content}


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
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Informe de YouTube sobre: {topic}"
    message["From"] = sender_email
    message["To"] = receiver_email

    # Adjuntamos el informe en formato HTML.
    # El cliente de correo renderizará este HTML en lugar de mostrarlo como texto plano.
    html_part = MIMEText(report, "html")
    message.attach(html_part)

    try:
        # Iniciamos la conexión con el servidor SMTP.
        print(f"Conectando al servidor SMTP en {host}:{port}...")
        server = smtplib.SMTP(host, port)
        server.starttls()  # Habilitamos la seguridad (cifrado)
        server.login(sender_email, password)
        
        # Enviamos el correo.
        server.sendmail(sender_email, receiver_email, message.as_string())
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