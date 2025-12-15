"""
Microsserviço Flask para ...
"""

from cronjob import cross_references, update_conta_arquivo_status
from logging.handlers import RotatingFileHandler
from upload_github import upload_file_to_github
from get_periods import read_periods_from_pdf, periodos_speds
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify
from parser import main as parser_main
from sentry import validar_requisicao
from initial import start_agent
from dotenv import load_dotenv
from flasgger import Swagger
from flask_cors import CORS
from pathlib import Path
from os import getenv
from re import search
import logging
import os
import tempfile
from db import test_connection
from speds import processa_sped


load_dotenv()

LOG_LEVEL = getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE_PATH = Path(getenv('LOG_FILE_PATH', 'logs/app.log')).expanduser()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

formatter = logging.Formatter(
  '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)

handler = RotatingFileHandler(
  LOG_FILE_PATH,
  maxBytes=int(getenv('LOG_MAX_BYTES', 1_000_000)),
  backupCount=int(getenv('LOG_BACKUP_COUNT', 3))
)
handler.setFormatter(formatter)
handler.setLevel(LOG_LEVEL)

logger = logging.getLogger('lpc_service')
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
logger.propagate = False

regex_data = r'\b\d{2}/\d{2}/\d{4}\b'

API_KEY_CURSOR = getenv('API_KEY_CURSOR')
app = Flask(__name__)

app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)

CORS(
  app, resources={
    r"/*": {
      "origins": "*",
      "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
      "allow_headers": ["Content-Type", "Authorization"]
    }
  }
)

swagger_config = {
  "headers": [],
  "specs": [
    {
      "endpoint": "apispec",
      "route": "/apispec.json",
      "rule_filter": lambda rule: True,
      "model_filter": lambda tag: True,
    }
  ],
  "static_url_path": "/flasgger_static",
  "swagger_ui": True,
  "specs_route": "/api-docs"
}

swagger_template = {
  "swagger": "2.0",
  "info": {
    "title": "Microsserviço para executar agentes Cursor",
    "description": "Microsserviço para executar agentes Cursor para processar arquivos de balancete (PDF)",
    "version": "1.0.0",
    "contact": {
      "name": "Support",
    }
  },
  "basePath": "/",
  "schemes": ["http", "https"],
  "consumes": ["application/json", "multipart/form-data"],
  "produces": ["application/json"]
}

swagger = Swagger(
  app, 
  config=swagger_config, 
  template=swagger_template
)


@app.before_request
def log_request():
  app.logger.info(
    "Requisicao recebida | metodo=%s | path=%s | ip=%s",
    request.method,
    request.path,
    request.remote_addr
  )


@app.after_request
def log_response(response):
  app.logger.info(
    "Resposta retornada | status=%s | metodo=%s | path=%s",
    response.status_code,
    request.method,
    request.path
  )
  return response


@app.route('/get-periods', methods=['POST'])
def get_periods():
  """
  Get Periods
  Obtém os períodos de um arquivo de balancete ou SPED
  ---
  tags:
    - Periods
  consumes:
    - multipart/form-data
  parameters:
    - in: formData
      name: file
      type: file
      required: true
      description: Arquivo de balancete (PDF) ou SPED (.txt) para análise
    - in: formData
      name: modelo
      type: string
      required: false
      default: balancete
      description: Modelo do arquivo: "balancete" (padrão) ou "sped"
  """
  if 'file' not in request.files:
    return jsonify({
      "status": "error",
      "message": "Campo 'file' é obrigatório na requisição."
    }), 400

  arquivo = request.files['file']

  if not arquivo or arquivo.filename == '':
    return jsonify({
      "status": "error",
      "message": "Arquivo não foi enviado ou está vazio."
    }), 400

  # Obter o parâmetro modelo, padrão é "balancete"
  modelo = request.form.get('modelo', 'balancete').lower()

  # Se o modelo for "sped", processar com periodos_speds
  if modelo == 'sped':
    try:
      # Criar arquivo temporário para o SPED
      with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
        temp_path = temp_file.name
        arquivo.save(temp_path)
      
      try:
        # Processar o arquivo SPED
        resultado = periodos_speds(temp_path)
        
        app.logger.info(
          "Periodos SPED processados com sucesso | filename=%s",
          arquivo.filename
        )
        
        return jsonify({
          "status": "success",
          "message": "Periods retrieved successfully",
          "periods": resultado.get('periodo', [])
        }), 200
        
      finally:
        # Remover arquivo temporário
        if os.path.exists(temp_path):
          os.unlink(temp_path)
          app.logger.debug("Arquivo temporário removido | path=%s", temp_path)
    
    except Exception as err:
      app.logger.warning(
        "Erro ao processar SPED para periodos | erro=%s",
        err
      )
      return jsonify({
        "status": "error",
        "message": str(err)
      }), 400

  # Processamento padrão para balancete (PDF)
  try:
    text_extracted = read_periods_from_pdf(arquivo)
  except ValueError as err:
    app.logger.warning(
      "Erro ao processar PDF para periodos | erro=%s",
      err
    )
    return jsonify({
      "status": "error",
      "message": str(err)
    }), 400

  soup = text_extracted.splitlines()
  datas_encontradas = []

  for linha in soup:
    if "Período" in linha:
      termos = linha.split()
      datas_encontradas.extend([
        item for item in termos if search(regex_data, item)
      ])

  return jsonify({
    "status": "success",
    "message": "Periods retrieved successfully",
    "periods": datas_encontradas
  }), 200


@app.route('/upload-file', methods=['POST'])
def upload_file():
  """
  Upload de Arquivo
  Recebe um arquivo de balancete e envia para o repositório GitHub configurado
  ---
  tags:
    - Upload
  consumes:
    - multipart/form-data
  parameters:
    - in: formData
      name: file
      type: file
      required: true
      description: Arquivo de balancete (PDF) a ser enviado para o GitHub
  responses:
    200:
      description: Arquivo enviado com sucesso
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
          message:
            type: string
            example: File uploaded successfully
    500:
      description: Falha ao enviar o arquivo
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: Failed to upload file
  """
  file = request.files['file']
  up = upload_file_to_github(file)

  status_code = up.get("status", 500) if isinstance(up, dict) else 500

  if status_code == 200 or status_code == 201:
    app.logger.info(
      "Upload realizado com sucesso no GitHub | status=%s",
      status_code
    )
    return jsonify({
      "status": status_code,
      "message": "File uploaded successfully",
      "detalhes": up.get("resultado") if isinstance(up, dict) else None,
    }), 200
  else:
    app.logger.error(
      "Falha ao enviar arquivo ao GitHub | status=%s | detalhes=%s",
      status_code,
      up
    )
    return jsonify({
      "status": status_code,
      "message": "Failed to upload file",
      "detalhes": up if not isinstance(up, dict) else up.get("resultado"),
    }), 500


@app.route('/save-file', methods=['POST'])
def save_file():
  """
  Salvar Arquivo Localmente
  Recebe um arquivo de balancete e salva na pasta parser-pdf
  ---
  tags:
    - Upload
  consumes:
    - multipart/form-data
  parameters:
    - in: formData
      name: file
      type: file
      required: true
      description: Arquivo de balancete (PDF) a ser salvo localmente
  responses:
    200:
      description: Arquivo salvo com sucesso
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
          message:
            type: string
            example: File saved successfully
          original_filename:
            type: string
            example: balancete original.pdf
          saved_filename:
            type: string
            example: balancete_original.pdf
          filename:
            type: string
            example: balancete_original.pdf
          path:
            type: string
            example: parser-pdf/balancete_original.pdf
          size:
            type: integer
            example: 1024576
    400:
      description: Arquivo não fornecido ou inválido
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: No file provided or invalid file
    500:
      description: Falha ao salvar o arquivo
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: Failed to save file
  """
  try:
    if 'file' not in request.files:
      app.logger.warning("Nenhum arquivo fornecido na requisição")
      return jsonify({
        "status": "error",
        "message": "No file provided"
      }), 400
    
    file = request.files['file']
    
    if file.filename == '':
      app.logger.warning("Nenhum arquivo selecionado")
      return jsonify({
        "status": "error",
        "message": "No file selected"
      }), 400
    
    if not file.filename.lower().endswith('.pdf'):
      app.logger.warning("Arquivo com extensão inválida: %s", file.filename)
      return jsonify({
        "status": "error",
        "message": "Only PDF files are allowed"
      }), 400
    
    upload_dir = Path('parser-pdf')
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    original_filename = file.filename
    filename = secure_filename(file.filename)
    
    file_path = upload_dir / filename
    counter = 1
    base_filename = filename
    while file_path.exists():
      name, ext = os.path.splitext(base_filename)
      filename = f"{name}_{counter}{ext}"
      file_path = upload_dir / filename
      counter += 1
    
    file.save(file_path)
    
    app.logger.info(
      "Arquivo salvo com sucesso | original_filename=%s | saved_filename=%s | path=%s",
      original_filename,
      filename,
      str(file_path)
    )
    
    return jsonify({
      "status": "success",
      "message": "File saved successfully",
      "original_filename": original_filename,
      "saved_filename": filename,
      "filename": filename,
      "path": str(file_path)
    }), 200
    
  except Exception as e:
    app.logger.error(
      "Erro ao salvar arquivo | error=%s",
      str(e)
    )
    return jsonify({
      "status": "error",
      "message": "Failed to save file",
      "details": str(e)
    }), 500


@app.route('/health', methods=['GET'])
def health_check():
  """
  Health Check Endpoint
  Verifica o status do serviço e se a API dos agentes Cursor está configurada
  ---
  tags:
    - Health
  responses:
    200:
      description: Serviço está funcionando
      schema:
        type: object
        properties:
          status:
            type: string
            example: healthy
          service:
            type: string
            example: Cursor Agent Processor
          cursor_configured:
            type: boolean
            example: true
  """
  return jsonify({
    "status": "healthy",
    "service": "Cursor Agent Processor",
    "cursor_configured": bool(API_KEY_CURSOR)
  }), 200


@app.route('/run-agent', methods=['POST'])
def run_agent():
  """
  Executar Agente Cursor
  Endpoint principal para acionar agentes do Cursor a partir de IDs existentes
  ---
  tags:
    - Cursor Agents
  consumes:
    - multipart/form-data
  parameters:
    - in: formData
      name: user_id
      type: integer
      required: true
      description: Identificador numérico do usuário proprietário do agente
    - in: formData
      name: file_id
      type: integer
      required: true
      description: Identificador numérico do arquivo vinculado ao agente
  responses:
    200:
      description: Execução do agente concluída com sucesso
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
    400:
      description: Erro na requisição (parâmetro ausente ou inválido)
      schema:
        type: object
        properties:
          error:
            type: string
            example: Erro de configuração
          message:
            type: string
            example: Campo 'user_id' é obrigatório e deve ser um inteiro.
    500:
      description: Erro interno durante a execução do agente
      schema:
        type: object
        properties:
          error:
            type: string
            example: Erro ao processar agente
          message:
            type: string
            example: Descrição detalhada do erro
  """
  try:
    user_id, file_id = validar_requisicao(request)
    start_agent(user_id, file_id)
    app.logger.info(
      "Agente iniciado com sucesso | user_id=%s | file_id=%s",
      user_id,
      file_id
    )
    return jsonify({
      "success": True,
      "message": "Agente iniciado com sucesso"
    }), 200

  except ValueError as e:
    app.logger.warning(
      "Erro de configuracao ao validar requisicao | detalhes=%s",
      e
    )
    return jsonify({
      "success": False,
      "message": "Erro de configuração",
      "errors": {
        "erro": str(e)
      }
    }), 400

  except Exception as e:
    app.logger.exception(
      "Erro interno ao executar agente | detalhes=%s",
      e
    )
    return jsonify({
      "success": False,
      "message": "Erro interno",
      "errors": {
        "erro": str(e)
      }
    }), 500


@app.route('/cronjob', methods=['POST'])
def cronjob():
  """
  Cronjob
  Executa a rotina que verifica e sincroniza agentes do Cursor
  ---
  tags:
    - Cronjob
  responses:
    200:
      description: Cronjob executado com sucesso
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
          message:
            type: string
            example: Cronjob executado com sucesso
          response:
            type: array
            items:
              type: object
            description: Detalhes retornados pelo verificador de agentes
    500:
      description: Falha ao executar o cronjob
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: Erro ao executar o cronjob
          response:
            type: array
            items:
              type: object
            description: Informações adicionais (se disponíveis)
  """
  try:
    parser_response = parser_main()
    
    if parser_response is None:
      app.logger.warning("Parser não retornou dados")
      return jsonify({
        "status": "error",
        "message": "Nenhum dado foi obtido do parser",
        "response": []
      }), 400
    
    processed_data = cross_references('')
    
    if processed_data is not None:
      app.logger.info("Cronjob executado com sucesso")
      return jsonify({
        "status": "success",
        "message": "Cronjob executado com sucesso",
        "response": processed_data
      }), 200
    else:
      app.logger.warning("Cronjob executado mas nenhum dado foi processado")
      return jsonify({
        "status": "success", 
        "message": "Cronjob executado mas nenhum dado foi processado",
        "response": []
      }), 200
      
  except Exception as e:
    app.logger.error(f"Erro ao executar cronjob: {str(e)}")
    return jsonify({
      "status": "error",
      "message": f"Erro ao executar cronjob: {str(e)}",
      "response": []
    }), 500


@app.route('/logs', methods=['GET'])
def get_logs():
  """
  Logs do Serviço
  Retorna as ultimas linhas do arquivo de logs do microsservico
  ---
  tags:
    - Logs
  parameters:
    - in: query
      name: limit
      type: integer
      required: false
      default: 200
      description: Quantidade de linhas mais recentes que devem ser retornadas (maximo 2000)
  responses:
    200:
      description: Logs retornados com sucesso
    404:
      description: Arquivo de log nao encontrado
  """
  limit = request.args.get('limit', default=200, type=int)

  if limit is None or limit <= 0:
    limit = 200

  limit = min(limit, 2000)

  if not LOG_FILE_PATH.exists():
    app.logger.warning(
      "Tentativa de acessar logs antes da geracao do arquivo | path=%s",
      LOG_FILE_PATH
    )
    return jsonify({
      "status": "error",
      "message": "Arquivo de log nao encontrado."
    }), 404

  with LOG_FILE_PATH.open('r', encoding='utf-8', errors='ignore') as logfile:
    linhas = logfile.readlines()

  return jsonify({
    "status": "success",
    "message": "Logs recuperados com sucesso",
    "limit": limit,
    "logs": [linha.rstrip('\n') for linha in linhas[-limit:]]
  }), 200


@app.route('/processar', methods=['POST'])
def processar():
  """"""
  try:
    if 'file' not in request.files:
      app.logger.warning("Nenhum arquivo fornecido na requisição")
      return jsonify({
        "status": "error",
        "message": "No file provided"
      }), 400
    
    file = request.files['file']
    
    if file.filename == '':
      app.logger.warning("Nenhum arquivo selecionado")
      return jsonify({
        "status": "error",
        "message": "No file selected"
      }), 400
    
    if not file.filename.lower().endswith('.pdf'):
      app.logger.warning("Arquivo com extensão inválida: %s", file.filename)
      return jsonify({
        "status": "error",
        "message": "Only PDF files are allowed"
      }), 400

    try:
      arquivo_id = request.form.get('arquivo_id')
      parser_response = parser_main(file)

      if parser_response is None:
        app.logger.warning("Parser não retornou dados")
        return jsonify({
          "status": "error",
          "message": "Nenhum dado foi obtido do parser",
          "response": []
        }), 400

      processed_data = cross_references(parser_response, arquivo_id)

      if processed_data:
        update_conta_arquivo_status(arquivo_id)
        app.logger.info("Cronjob executado com sucesso")
        return jsonify({
          "status": "success",
          "message": "Cronjob executado com sucesso"
        }), 200
      else:
        app.logger.warning("Cronjob executado mas nenhum dado foi processado")
        return jsonify({
          "status": "success", 
          "message": "Cronjob executado mas nenhum dado foi processado",
          "response": []
        }), 200
        
    except Exception as e:
      app.logger.error(f"Erro ao executar cronjob: {str(e)}")
      return jsonify({
        "status": "error",
        "message": f"Erro ao executar cronjob: {str(e)}",
        "response": []
      }), 500
    
  except Exception as e:
    app.logger.error("Erro ao processar arquivo | error=%s", str(e))
    return jsonify({
      "status": "error",
      "message": "Failed to process file",
      "details": str(e)
    }), 500


@app.route('/processar-sped', methods=['POST'])
def processar_sped():
  """
  Processar SPED
  Recebe um arquivo SPED e processa extraindo informações dos registros M210 e M610
  ---
  tags:
    - SPED
  consumes:
    - multipart/form-data
  parameters:
    - in: formData
      name: file
      type: file
      required: true
      description: Arquivo SPED (.txt) para processamento
  responses:
    200:
      description: Arquivo SPED processado com sucesso
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
          message:
            type: string
            example: Arquivo SPED processado com sucesso
          data:
            type: object
            properties:
              m210:
                type: array
                items:
                  type: string
                description: Campos do registro M210
              m610:
                type: array
                items:
                  type: string
                description: Campos do registro M610
    400:
      description: Arquivo não fornecido ou inválido
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: Campo 'file' é obrigatório na requisição.
    500:
      description: Erro ao processar o arquivo SPED
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: Erro ao processar arquivo SPED
          details:
            type: string
            example: Descrição detalhada do erro
  """
  try:
    if 'file' not in request.files:
      app.logger.warning("Nenhum arquivo fornecido na requisição de SPED")
      return jsonify({
        "status": "error",
        "message": "Campo 'file' é obrigatório na requisição."
      }), 400
    
    arquivo_sped = request.files['file']
    
    if not arquivo_sped or arquivo_sped.filename == '':
      app.logger.warning("Arquivo SPED não foi enviado ou está vazio")
      return jsonify({
        "status": "error",
        "message": "Arquivo SPED não foi enviado ou está vazio."
      }), 400
    
    # Criar arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
      temp_path = temp_file.name
      arquivo_sped.save(temp_path)
    
    try:
      # Processar o arquivo SPED
      resultado = processa_sped(temp_path)
      
      app.logger.info(
        "Arquivo SPED processado com sucesso | filename=%s",
        arquivo_sped.filename
      )
      
      return jsonify({
        "status": "success",
        "message": "Arquivo SPED processado com sucesso",
        "data": resultado
      }), 200
      
    finally:
      # Remover arquivo temporário
      if os.path.exists(temp_path):
        os.unlink(temp_path)
        app.logger.debug("Arquivo temporário removido | path=%s", temp_path)
    
  except Exception as e:
    app.logger.error(
      "Erro ao processar arquivo SPED | error=%s",
      str(e)
    )
    return jsonify({
      "status": "error",
      "message": "Erro ao processar arquivo SPED",
      "details": str(e)
    }), 500


@app.route('/', methods=['GET'])
def index():
  """
  Página Inicial / Documentação
  Fornece um resumo do microsserviço e dos endpoints disponíveis
  ---
  tags:
    - Documentation
  responses:
    200:
      description: Informações básicas do microsserviço
      schema:
        type: object
        properties:
          service:
            type: string
            example: Cursor Agent Processor
          description:
            type: string
            example: Microsserviço Flask para executar agentes Cursor vinculados a PDFs.
          version:
            type: string
            example: 1.0.0
          endpoints:
            type: object
            additionalProperties:
              type: string
            example:
              GET /health: Verifica o status do serviço e a configuração Cursor
              POST /run-agent: Executa um agente Cursor para um arquivo vinculado
              POST /cronjob: Sincroniza agentes Cursor agendados
              GET /api-docs: Interface Swagger com documentação interativa
          swagger_ui:
            type: string
            example: http://localhost:5000/api-docs
  """
  return jsonify({
    "service": "Cursor Agent Processor",
    "description": "Microsserviço Flask responsável por orquestrar agentes Cursor vinculados a arquivos de balancete.",
    "version": "1.0.0",
    "endpoints": {
      "GET /health": "Verifica o status do serviço e a configuração Cursor.",
      "POST /run-agent": "Executa um agente Cursor vinculado a um arquivo.",
      "POST /cronjob": "Sincroniza agentes Cursor agendados.",
      "GET /api-docs": "Interface Swagger para explorar a API."
    },
    "swagger_ui": "http://localhost:5000/api-docs"
  }), 200


if __name__ == '__main__':
  if not API_KEY_CURSOR:
    print("⚠️  AVISO: API_KEY_CURSOR não configurada!")
    print("Configure-a como variável de ambiente")
    print("O serviço iniciará, mas o endpoint /process-pdf não funcionará.")
  
  app.logger.info(
    "Servico iniciado | host=%s | port=%s | debug=%s | log_file=%s",
    '0.0.0.0',
    getenv('PORT', 5000),
    getenv('FLASK_DEBUG', 'False').lower() == 'true',
    LOG_FILE_PATH
  )

  if test_connection():
    app.logger.info("Conexao com o banco de dados estabelecida")
  else:
    app.logger.error("Erro ao conectar ao banco de dados")
    exit(1)

  app.run(
    host='0.0.0.0',
    port=int(getenv('PORT', 5000)),
    debug=getenv('FLASK_DEBUG', 'False').lower() == 'true'
  )
