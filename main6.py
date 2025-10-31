# Este arquivo é para transformar o arquivo xlsx em zip, e depois extrair o conteúdo do zip

import zipfile
from pathlib import Path
import shutil

def transformar_xlsx_em_zip(arquivo):
    arquivo_xlsx = Path(arquivo)

    zip_path = arquivo_xlsx.with_suffix(".zip")
    temporario = Path("temp")

    shutil.copy(arquivo_xlsx, zip_path)

    if temporario.exists():
        shutil.rmtree(temporario)
    temporario.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temporario)

# transformar_xlsx_em_zip('balancete-9.xlsx')
