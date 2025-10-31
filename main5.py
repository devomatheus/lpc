# Este arquivo será para encontrar o arquivo XML com 8 colunas

import xml.etree.ElementTree as ET
from pathlib import Path

temporario = Path("temp")
pasta = temporario / "xl" / "worksheets"
ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
arquivos_xml = list(pasta.glob("*.xml"))
arquivo_8_cols = None

def encontra_arquivo():
    if not arquivos_xml:
        print("Nenhum arquivo XML encontrado na pasta.")
        return
    
    print(f"Analisando {len(arquivos_xml)} arquivo(s) XML...")
    
    for arquivo in arquivos_xml:
        try:
            tree = ET.parse(arquivo)
            root = tree.getroot()
            cols_tag = root.find('main:cols', ns)
            
            if cols_tag is not None:
                qtd_cols = len(cols_tag.findall('main:col', ns))
                
                if qtd_cols == 8:
                    arquivo_8_cols = arquivo      
        except Exception as e:
            print(f"Erro em {arquivo.name}: {e}")
    
    return arquivo_8_cols
