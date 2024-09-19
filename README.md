# Monitor de Rodajes

Este script en Python realiza scraping en la página web del Ministerio de Cultura de España para detectar cambios en la sección de rodajes. Cuando se detecta un nuevo documento, el script descarga el PDF actualizado, compara su contenido con la versión anterior y envía un correo electrónico con las diferencias encontradas.

## Requisitos

- **Python**: 3.x
- **Bibliotecas**:
  - `requests`
  - `beautifulsoup4`
  - `PyPDF2`
  - `openai`
  - `smtplib`

## Configuración

1. **Variables de Entorno**: Define las siguientes variables en un archivo `.env` o en tus variables de entorno:
   - `EMAIL_USER`: Tu dirección de correo electrónico.
   - `EMAIL_PASS`: Tu contraseña de correo electrónico.
   - `EMAIL_RECV`: Dirección de correo electrónico del destinatario.
   - `OPENAI_API_KEY`: Tu clave API de OpenAI.

2. **Instalación de Dependencias**: Instala las dependencias necesarias utilizando pip:
   ```bash
   pip install requests beautifulsoup4 PyPDF2 openai
   ```

3. **Ejecución del Script**: Puedes ejecutar el script manualmente o configurarlo en un cron job. Un ejemplo de cron job para ejecutarlo cada 4 horas:
   ```bash
   0 */4 * * * source /home/ubuntu/py_scripts/.env && echo "\n[$(date)] Inicio de la ejecución del script:" >> /home/ubuntu/log.log; /usr/bin/python3 /home/ubuntu/py_scripts/monitor_rodajes.py >> /home/ubuntu/log.log 2>&1
   ```

## Funcionamiento

- El script verifica la página de rodajes en busca de cambios.
- Si se detecta un nuevo PDF, se descarga y se compara con la versión anterior.
- Las diferencias se envían por correo electrónico al destinatario especificado.

## Registro de Errores

Los errores y eventos se registran en el archivo `monitor_de_rodajes.log`.

## Contribuciones

Las contribuciones son bienvenidas. Abre un issue o un pull request para discutir cambios.

## Licencia

Este proyecto está bajo la Licencia MIT.
