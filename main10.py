import os
import json
import requests
from pathlib import Path


def enviar_requisicao_para_api(prompt_text, api_url, api_key, repository, ref="main", output_dir="temp", output_filename="resposta.json"):
    """
    Envia uma requisição para a API do Cursor Agents com um prompt.
    O arquivo será lido diretamente do repositório GitHub configurado.
    
    Args:
        prompt_text: Texto do prompt
        api_url: URL do endpoint da API
        api_key: Chave de API
        repository: URL do repositório GitHub
        ref: Branch do repositório (padrão: main)
        output_dir: Diretório onde salvar o JSON de resposta
        output_filename: Nome do arquivo JSON de saída
    
    Returns:
        dict: Resposta JSON da API
    """
    # Criar diretório de saída se não existir
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Preparar headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # Estrutura de dados conforme a documentação da API do Cursor
        # O PDF será lido diretamente do repositório GitHub configurado
        payload = {
            "prompt": {
                "text": prompt_text
            },
            "source": {
                "repository": repository,
                "ref": ref
            }
        }
        
        # Fazer requisição POST
        print(f"Enviando requisição para API do Cursor...")
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=300
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
    PROMPT_TEXT = "Read the PDF file called balancete.pdf located in my lpc repository; it contains a table. Retrieve the data from the table in JSON format."
    
    # URL da API do Cursor
    API_URL = os.getenv("CURSOR_API_URL", "https://api.cursor.com/v0/agents")
    
    # API Key (pode ser definida como variável de ambiente)
    API_KEY = os.getenv("API_KEY_CURSOR", "key_7962e3c61cbc93fcbde53a96dc96b965885f9ca6569613069ff29fef44af296a")
    
    # Informações do repositório GitHub
    REPOSITORY = "https://github.com/devomatheus/lpc"
    REF = "main"
    
    # Diretório de saída
    OUTPUT_DIR = "temp"
    OUTPUT_FILENAME = "resposta_api.json"
    
    try:
        resultado = enviar_requisicao_para_api(
            prompt_text=PROMPT_TEXT,
            api_url=API_URL,
            api_key=API_KEY,
            repository=REPOSITORY,
            ref=REF,
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
