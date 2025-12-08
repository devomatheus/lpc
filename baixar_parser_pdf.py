from dotenv import load_dotenv
from base64 import b64decode
from requests import get
from os import getenv


load_dotenv()


def download_parser_pdf(branch):
    OWNER = getenv("OWNER", None)
    REPO = getenv("REPO", None)
    TOKEN = getenv("TOKEN_GITHUB", None)
    FILE_PATH = getenv("FILE_PATH", None)
    API_GITHUB_ROOT = getenv("API_GITHUB_ROOT", None)

    url = f"{API_GITHUB_ROOT}/{OWNER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    params = {"ref": branch}

    response = get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        file_content = b64decode(data["content"])

        with open("temp/balancete.json", "wb") as f:
            f.write(file_content)

        print("PDF baixado com sucesso!")
        return True
    
    return False
