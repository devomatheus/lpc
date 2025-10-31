import os
import json
import requests
from pathlib import Path
from typing import Optional


def enviar_pdf_para_api(pdf_path, prompt, api_url, api_key = None, output_dir = "temp", output_filename = "resposta.json"):
    """
    Envia um arquivo PDF para a API do Cursor com um prompt e salva a resposta JSON.
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        prompt: Prompt/texto a ser enviado junto com o PDF
        api_url: URL do endpoint da API
        api_key: Chave de API (opcional, pode ser passada via header ou query)
        output_dir: Diretório onde salvar o JSON de resposta
        output_filename: Nome do arquivo JSON de saída
    
    Returns:
        dict: Resposta JSON da API
    """
    # Verificar se o arquivo PDF existe
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
    
    # Criar diretório de saída se não existir
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Preparar headers
    headers = {
        "Accept": "application/json",
    }
    
    # Adicionar API key se fornecida
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        # Ou use header específico dependendo da API:
        # headers["X-API-Key"] = api_key
    
    # Abrir arquivo PDF em modo binário
    try:
        with open(pdf_path, 'rb') as pdf_file:
            # Preparar dados para multipart/form-data
            files = {
                'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')
            }
            
            data = {
                'prompt': prompt
            }
            
            # Fazer requisição POST
            print(f"Enviando arquivo {pdf_path} para a API...")
            response = requests.post(
                api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=300  # Timeout de 5 minutos para processamento
            )
            
            # Verificar resposta
            response.raise_for_status()
            
            # Converter resposta para JSON
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                # Se não for JSON, salvar como texto
                response_json = {"resposta_texto": response.text}
            
            # Salvar JSON no arquivo
            json_file_path = output_path / output_filename
            with open(json_file_path, 'w', encoding='utf-8') as json_file:
                json.dump(response_json, json_file, ensure_ascii=False, indent=2)
            
            print(f"✓ Resposta salva em: {json_file_path}")
            return response_json
            
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Resposta: {e.response.text}")
        raise
    except Exception as e:
        print(f"Erro ao processar: {e}")
        raise


def main():
    """
    Função principal - configure aqui os parâmetros da sua requisição
    """
    # Configurações
    PDF_PATH = "balancete-9.pdf"  # Caminho para o arquivo PDF
    PROMPT = "Analise este documento e extraia informações relevantes em formato JSON estruturado."
    
    # URL da API do Cursor (substitua pela URL real)
    # Exemplos de possíveis endpoints:
    API_URL = os.getenv("CURSOR_API_URL", "https://api.cursor.sh/v1/chat/completions")
    
    # API Key (pode ser definida como variável de ambiente)
    API_KEY = os.getenv("CURSOR_API_KEY", None)
    
    # Diretório de saída
    OUTPUT_DIR = "temp"
    OUTPUT_FILENAME = "resposta_api.json"
    
    try:
        resultado = enviar_pdf_para_api(
            pdf_path=PDF_PATH,
            prompt=PROMPT,
            api_url=API_URL,
            api_key=API_KEY,
            output_dir=OUTPUT_DIR,
            output_filename=OUTPUT_FILENAME
        )
        
        print("\n✓ Processo concluído com sucesso!")
        print(f"Total de chaves no JSON: {len(resultado)}")
        
    except Exception as e:
        print(f"\n✗ Erro ao executar: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
