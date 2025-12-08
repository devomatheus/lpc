from base64 import b64encode
from os import getenv


from dotenv import load_dotenv
from requests import get, put

try:
    from werkzeug.datastructures import FileStorage
except ImportError:
    FileStorage = None


load_dotenv()

OWNER = getenv("OWNER")
REPO = getenv("REPO")
TOKEN = getenv("TOKEN_GITHUB")
BRANCH = getenv("BRANCH")


def _extrair_dados_de_filestorage(file):
    nome_arquivo = getattr(file, "filename", None)
    tipo_arquivo = getattr(file, "mimetype", None) or getattr(file, "content_type", None)

    if not nome_arquivo:
        raise ValueError("Nome do arquivo não informado.")

    conteudo_bytes = file.read()
    if not conteudo_bytes:
        raise ValueError("Conteúdo do arquivo não informado.")

    if hasattr(file, "stream") and hasattr(file.stream, "seek"):
        try:
            file.stream.seek(0)
        except (OSError, ValueError):
            pass

    base64_content = b64encode(conteudo_bytes).decode("utf-8")
    return nome_arquivo, tipo_arquivo, base64_content


def _extrair_dados_de_dict(file):
    nome_arquivo = file.get("nome")
    tipo_arquivo = file.get("tipo")
    conteudo = file.get("conteudo")

    if not nome_arquivo:
        raise ValueError("Nome do arquivo não informado.")

    if conteudo is None:
        raise ValueError("Conteúdo do arquivo não informado.")

    if isinstance(conteudo, str):
        base64_content = "".join(conteudo.splitlines())
    else:
        base64_content = b64encode(conteudo).decode("utf-8")

    return nome_arquivo, tipo_arquivo, base64_content


def _extrair_informacoes(file):
    if FileStorage is not None and isinstance(file, FileStorage):
        return _extrair_dados_de_filestorage(file)

    if isinstance(file, dict):
        return _extrair_dados_de_dict(file)

    if hasattr(file, "read") and hasattr(file, "filename"):
        return _extrair_dados_de_filestorage(file)

    raise TypeError(
        "Tipo de objeto não suportado para upload. Esperado dict ou FileStorage."
    )


def upload_file_to_github(file):
    if not file:
        raise ValueError("Arquivo não fornecido.")

    nome_arquivo, tipo_arquivo, base64_content = _extrair_informacoes(file)

    if tipo_arquivo and "pdf" not in tipo_arquivo.lower() and tipo_arquivo != "Balancete":
        raise ValueError(
            'Tipo do arquivo não suportado. Apenas arquivos PDF ou do tipo "Balancete" podem ser processados.'
        )

    file_path = f"{nome_arquivo}"
    github_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{file_path}"
    check_url = (
        f"{github_url}?ref={BRANCH}" if BRANCH else github_url
    )

    auth_headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    check_response = get(check_url, headers=auth_headers, timeout=30)

    sha = None
    if check_response.status_code == 200:
        check_data = check_response.json()
        sha = check_data.get("sha")

    upload_data = {
        "message": f"Adiciona arquivo {nome_arquivo}",
        "content": base64_content,
    }

    if BRANCH:
        upload_data["branch"] = BRANCH

    if sha:
        upload_data["sha"] = sha

    upload_headers = {
        **auth_headers,
        "Content-Type": "application/json",
    }

    upload_response = put(
        github_url,
        headers=upload_headers,
        json=upload_data,
        timeout=30,
    )

    if not upload_response.ok:
        try:
            error_message = upload_response.json().get("message", "")
        except ValueError:
            error_message = upload_response.text
        raise RuntimeError(f"Erro ao fazer upload para o GitHub: {error_message}")

    upload_result = upload_response.json()
    return {
        "status": upload_response.status_code,
        "resultado": upload_result,
        "caminho": file_path,
        "repositorio": f"{OWNER}/{REPO}",
    }
