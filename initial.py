from requests.exceptions import RequestException
from db import test_connection, execute_query
from json import JSONDecodeError
from dotenv import load_dotenv
from requests import post
from os import getenv


load_dotenv()

API_URL = getenv("CURSOR_API_URL", None)
API_KEY = getenv("API_KEY_CURSOR", None)
REPOSITORY = getenv("REPOSITORIO", None)
REF = getenv("REF", None)
MODEL = getenv("CURSOR_MODEL", None)
PROMPT = """
    You are a data extraction and document analysis assistant.
    Your task is to parse and convert the content of a financial report PDF into a structured JSON file.
    The file to be parsed is located at:
    **`parser-pdf/balancete.pdf`**

    Follow these strict rules:

    1. **Read and interpret all content**, including:

    * Header information (e.g., company name, CNPJ, date, time, report title, reporting period, page number, etc.).
    * All tabular data, even when tables are split, misaligned, or inconsistently formatted.
    * Text that appears outside tables but represents meaningful data (such as account categories or summaries).

    2. **Bold or emphasized text must never be ignored.**
    Treat bold or highlighted words as essential — they often represent key categories or headers that must appear in the final JSON.
    Some of these bold elements might not have numeric codes, so ensure they are **captured and properly associated** with the relevant data entries.

    3. **Recognize and preserve hierarchy.**
    Many entries represent subaccounts or nested categories.
    Use visual indentation, numeric account codes (e.g., `3.3.01.050.01`), and textual grouping to determine:

    * Parent accounts (main categories)
    * Child accounts (subcategories)

    4. **Generate a complete and organized JSON structure** with the following format:

    ```json
    {
        "header": {
        "company": "ZUCO FORTE TRANSPORTES LTDA",
        "cnpj": "47.299.647/0001-20",
        "report_type": "BALANCETE CONSOLIDADO",
        "period": "01/01/2025 - 30/06/2025",
        "issue_date": "27/10/2025",
        "time": "15:00:57",
        "page": "1",
        "book_number": "0001"
        },
        "data": [
        {
            "code": "52665",
            "classification": "3.3.01.050.01",
            "account": "DEPRECIAÇÃO MÓVEIS, UTENSÍLIOS E EQUIPAMENTOS",
            "previous_balance": "0,00",
            "current_balance": "9.330,41",
            "debit": "9.330,41",
            "credit": "0,00",
            "parent_category": "DEPRECIAÇÃO"
        }
        ]
    }
    ```

    5. **Data normalization rules:**

    * Remove unnecessary whitespace.
    * Keep all numeric values as strings (do not replace commas with dots).
    * Preserve Portuguese account names exactly as they appear.
    * Keep the natural order of the data as in the document.
    * If a field is missing or empty, assign `null` as its value.

    6. **Do not omit any element** — all bold labels, headers, rows, and totals must be represented in the JSON.
    Ensure nothing from the original PDF is lost, even if visually separated or formatted differently.

    7. **Output only the final JSON**, fully representing all parsed information from `parser-pdf/balancete.pdf`.

    8. balancete.json. This filename is mandatory and must not be altered.
"""

headers = {
    "Content-Type": "application/json"
}


def send_request_to_cursor(prompt, api_url, api_key, repo, ref, model):
    """
    Envia uma requisição para a API do Cursor Agents com um prompt.
    O arquivo será lido diretamente do repositório GitHub configurado.
    
    Args:
        prompt_text: Texto do prompt
        api_url: URL do endpoint da API
        api_key: Chave de API
        repository: URL do repositório GitHub
        ref: Branch base do repositório (padrão: main)
        branch_name: Nome da branch que será criada (opcional)
        model: Nome do modelo a ser usado (opcional, ex: "gpt-4", "claude-3-opus", "auto")
        output_dir: Diretório onde salvar o JSON de resposta
        output_filename: Nome do arquivo JSON de saída
    
    Returns:
        dict: Resposta JSON da API
    """
    # A API do Cursor usa Basic Authentication, não Bearer Token
    # No requests, isso é feito com auth=(api_key, '') onde a senha é vazia
    auth = (api_key, '')
    
    try:
        payload = {
            "prompt": {
                "text": prompt
            },
            "source": {
                "repository": repo,
                "ref": ref
            }
        }
        
        if model:
            payload["model"] = model
        
        print(f"Enviando requisição para API do Cursor...")
        response = post(api_url, json=payload, headers=headers, auth=auth, timeout=300)
        
        response.raise_for_status()
        
        try:
            response_json = response.json()
        except JSONDecodeError:
            response_json = {"resposta_texto": response.text}
        
        return response_json
        
    except RequestException as e:
        print(f"Erro na requisição: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Resposta: {e.response.text}")
        raise

    except Exception as e:
        print(f"Erro ao processar: {e}")
        raise


def start_agent(user_id, file_id):
    """
    Função principal - configure aqui os parâmetros da sua requisição
    """
    try:
        resultado = send_request_to_cursor(PROMPT, API_URL, API_KEY, REPOSITORY, REF, MODEL)
        id_agente = resultado.get("id", None)
        status = resultado.get("status", None)
        branch = resultado.get("target", {}).get("branchName", None)
        url_branch = resultado.get("target", {}).get("url", None)

        if test_connection():
            execute_query(
                """INSERT INTO agentes (
                    status, branch, url_branch, usuario_id, arquivo_id, id_agente
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (status, branch, url_branch, user_id, file_id, id_agente),
                fetch=False
            )
            print("✓ Dados inseridos com sucesso!")

    except Exception as e:
        print(f"\n✗ Erro ao executar: {e}")
        return 1
    
    return 0
