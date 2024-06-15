#!/usr/bin/python3
import os
import requests
from bs4 import BeautifulSoup
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from urllib.parse import urljoin
from PyPDF2 import PdfReader
from openai import OpenAI

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


class PDFDownloader:
    @staticmethod
    def descargar_pdf(url, path):
        try:
            full_url = urljoin(URL, url)
            response = requests.get(full_url, stream=True, verify=False)
            if response.status_code == 200:
                with open(path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return path
            else:
                logging.error(f'Error al descargar el PDF. Código de respuesta: {response.status_code}')
                return None
        except Exception as e:
            logging.error(f'Excepción al descargar el PDF: {e}')
            return None


class PDFComparer:
    @staticmethod
    def extract_text_from_pdf(pdf_path):
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            logging.error(f'Error al extraer texto del PDF: {e}')
            return ""

    @staticmethod
    def compare_texts(text1, text2):
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
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en comparar listas de datos estructurados."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f'Error al comparar textos con la API de OpenAI: {e}')
            return ""


class EmailSender:
    @staticmethod
    def enviar_email(href, texto, differences, pdf_path=None):
        logging.info("Enviando email...")
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_USER
            msg['To'] = EMAIL_RECV
            msg['Subject'] = 'Notificación de cambio en Rodajes'

            body = f'Se han detectado cambios en la página de rodajes:\n{href}\nTexto: {texto}\n\nDiferencias encontradas:\n{differences}'
            msg.attach(MIMEText(body, 'plain'))

            if pdf_path:
                part = MIMEBase('application', 'octet-stream')
                with open(pdf_path, 'rb') as file:
                    part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_path)}')
                msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_RECV, msg.as_string())
            server.quit()
        except smtplib.SMTPAuthenticationError:
            logging.error("Error de autenticación con el servidor SMTP. Revisa tus credenciales.")
            os.remove(STATE_FILE)
        except smtplib.SMTPException as e:
            logging.error(f"Error al enviar el email: {e}")
            os.remove(STATE_FILE)
        except Exception as e:
            logging.error(f"Error inesperado al enviar el email: {e}")
            os.remove(STATE_FILE)


class CambioRodajesMonitor:
    @staticmethod
    def verificar_cambio_y_notificar():
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
                        os.makedirs('/home/ubuntu/py_scripts/pdf', exist_ok=True)
                        pdf_path_actual = '/home/ubuntu/py_scripts/pdf/rodajes_actual.pdf'
                        pdf_path_anterior = '/home/ubuntu/py_scripts/pdf/rodajes_anterior.pdf'
                        PDFDownloader.descargar_pdf(href_actual, pdf_path_actual)

                        if os.path.exists(pdf_path_anterior):
                            text1 = PDFComparer.extract_text_from_pdf(pdf_path_anterior)
                            text2 = PDFComparer.extract_text_from_pdf(pdf_path_actual)
                            differences = PDFComparer.compare_texts(text1, text2)
                        else:
                            differences = "No se encontró un PDF anterior para comparar."

                        logging.info(f'Diferencias encontradas:\n{differences}')
                        EmailSender.enviar_email(href_actual, texto_actual, differences, pdf_path_actual)

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
CambioRodajesMonitor.verificar_cambio_y_notificar()
