import xml.etree.ElementTree as ET
from pathlib import Path
import zipfile
import shutil

# Caminho do arquivo Excel original
xlsx_path = Path("balancete_teste.xlsx")

# Criar paths derivados
zip_path = xlsx_path.with_suffix(".zip")
extract_dir = Path("temp")

# 1️⃣ Converter .xlsx para .zip
shutil.copy(xlsx_path, zip_path)

# 2️⃣ Descompactar o conteúdo do zip
if extract_dir.exists():
    shutil.rmtree(extract_dir)
extract_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(extract_dir)

print(f"📦 Arquivos extraídos em: {extract_dir.resolve()}")

# 3️⃣ Definir caminhos dos XMLs principais
sheet_path = extract_dir / "xl" / "worksheets" / "sheet1.xml"
shared_path = extract_dir / "xl" / "sharedStrings.xml"


if sheet_path.exists():
    tree = ET.parse(sheet_path)
    root = tree.getroot()

    for row in root.findall(".//{*}row")[:5]:
        for cell in row.findall("{*}c"):
            ref = cell.attrib.get("r")
            val = cell.find("{*}v")
            tipo = cell.attrib.get("t")
            valor = val.text if val is not None else ""
            print(f"  - {ref}: {valor} (tipo={tipo})")


# if shared_path.exists():
#     tree = ET.parse(shared_path)
#     root = tree.getroot()
#     strings = [t.text for t in root.findall(".//{*}t")]
    
#     for i, text in enumerate(strings[:10]):
#         print(f"  [{i}] {text}")

# 6️⃣ Limpeza opcional
# zip_path.unlink(missing_ok=True)
