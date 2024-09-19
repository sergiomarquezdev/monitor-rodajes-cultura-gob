#!/usr/bin/python3
import os
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
from PyPDF2 import PdfReader
from openai import OpenAI
from typing import Optional, Tuple

# Configuración de logging
logging.basicConfig(filename='/home/ubuntu/py_scripts/monitor_de_rodajes.log', level=logging.DEBUG,
                    format='%(asctime)s %(message)s')

# Uso de variables de entorno para datos sensibles
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_RECV = os.getenv('EMAIL_RECV')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configura tu clave API de OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Constantes de configuración
URL = 'https://www.cultura.gob.es/en/cultura/areas/cine/datos/rodajes.html'
STATE_FILE = '/home/ubuntu/py_scripts/estado_rodajes.txt'
HISTORY_FILE = '/home/ubuntu/py_scripts/historial_rodajes.txt'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'


def descargar_pdf(url: str, path: str) -> Optional[str]:
    """Descarga un PDF desde la URL especificada y lo guarda en el path dado."""
    full_url = urljoin(URL, url)
    response = requests.get(full_url, stream=True, verify=False)
    if response.status_code == 200:
        with open(path, 'wb') as file:
            file.write(response.content)
        return path
    logging.error(f'Error al descargar el PDF. Código de respuesta: {response.status_code}')
    return None


def extraer_texto_pdf(pdf_path: str) -> str:
    """Extrae el texto de un PDF dado."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            return ''.join(page.extract_text() for page in reader.pages)
    except Exception as e:
        logging.error(f'Error al extraer texto del PDF: {e}')
        return ""


def comparar_textos(text1: str, text2: str) -> str:
    """Compara dos textos y devuelve las diferencias utilizando la API de OpenAI."""
    prompt = f"""
        Estos son PDFs que se actualizan cada pocos días y contienen los rodajes notificados al ICAA, organizados por año y mes.
        En cada PDF, los rodajes están divididos en tablas por meses, y cada mes tiene una tabla con las siguientes columnas:
        - TÍTULO
        - PRODUCTORA
        - DIRECCIÓN
        - INICIO RODAJE
        - FIN RODAJE

        Tengo dos listas de rodajes extraídas de estos PDFs. La primera lista es de una versión anterior del PDF y la segunda lista es de una versión más reciente del PDF. Quiero que compares las dos listas y me indiques los nuevos registros que se han añadido en la versión más reciente. Los nuevos registros deben destacarse con las diferencias en:
        - TÍTULO
        - PRODUCTORA
        - DIRECCIÓN
        - INICIO RODAJE
        - FIN RODAJE

        Si no hay diferencias, simplemente responde con: "No se han encontrado diferencias."

        A continuación se presentan los textos a comparar:

        Texto 1 (versión anterior):
        {text1}

        Texto 2 (versión más reciente):
        {text2}

        Nuevos registros añadidos:
        """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un experto en comparar listas de datos estructurados."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f'Error al comparar textos con la API de OpenAI: {e}')
        return ""


def enviar_email(href: str, texto: str, diferencias: str, pdf_path: Optional[str] = None):
    """Envía un correo electrónico con las diferencias encontradas."""
    logging.info("Enviando email...")
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders

        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECV
        msg['Subject'] = 'Notificación de cambio en Rodajes'

        body = f'Se han detectado cambios en la página de rodajes:\n{href}\nTexto: {texto}\n\nDiferencias encontradas:\n{diferencias}'
        msg.attach(MIMEText(body, 'plain'))

        if pdf_path:
            part = MIMEBase('application', 'octet-stream')
            with open(pdf_path, 'rb') as file:
                part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_path)}')
            msg.attach(part)

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_RECV, msg.as_string())
    except Exception as e:
        logging.error(f"Error al enviar el email: {e}")


def verificar_cambio_y_notificar():
    """Verifica cambios en la página de rodajes y notifica por email si hay cambios."""
    logging.info("\nComenzando la verificación de cambios.")
    try:
        with open(STATE_FILE, 'r') as file:
            ultimo_href, ultimo_texto = file.read().strip().split('\n')
    except FileNotFoundError:
        ultimo_href, ultimo_texto = '', ''

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})

    try:
        respuesta = session.get(URL, verify=False)
        if respuesta.status_code == 200:
            soup = BeautifulSoup(respuesta.content, 'html.parser')
            primer_elemento = soup.select_one('.elemento a')
            if primer_elemento:
                href_actual = primer_elemento['href']
                texto_actual = primer_elemento.get_text(strip=True)
                if href_actual != ultimo_href or texto_actual != ultimo_texto:
                    logging.info(f'El enlace ha cambiado a: {href_actual} con texto "{texto_actual}"')
                    pdf_path_actual = '/home/ubuntu/py_scripts/pdf/rodajes_actual.pdf'
                    pdf_path_anterior = '/home/ubuntu/py_scripts/pdf/rodajes_anterior.pdf'
                    descargar_pdf(href_actual, pdf_path_actual)

                    if os.path.exists(pdf_path_anterior):
                        text1 = extraer_texto_pdf(pdf_path_anterior)
                        text2 = extraer_texto_pdf(pdf_path_actual)
                        diferencias = comparar_textos(text1, text2)
                    else:
                        diferencias = "No se encontró un PDF anterior para comparar."

                    logging.info(f'Diferencias encontradas:\n{diferencias}')
                    enviar_email(href_actual, texto_actual, diferencias, pdf_path_actual)

                    # Renombrar el PDF actual a PDF anterior después de enviar el correo
                    if os.path.exists(pdf_path_anterior):
                        os.remove(pdf_path_anterior)
                    os.rename(pdf_path_actual, pdf_path_anterior)

                    with open(STATE_FILE, 'w') as file:
                        file.write(f'{href_actual}\n{texto_actual}')
                    with open(HISTORY_FILE, 'a') as history_file:
                        history_file.write(f'{href_actual}\n{texto_actual}\n')
        else:
            logging.error(f'Error al hacer la solicitud: Código de estado {respuesta.status_code}')
    except requests.exceptions.RequestException as e:
        logging.error(f'Error de red o HTTP al intentar acceder a la página: {e}')


# Ejecutar la verificación y notificación
if __name__ == "__main__":
    verificar_cambio_y_notificar()
