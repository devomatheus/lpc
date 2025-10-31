# este arquivo será para ler e transformar os dados de sharedstrings.xml em um dicionário

import xml.etree.ElementTree as ET
from pathlib import Path
from json import dump

namespace = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def xml_para_dict(xml_file_path):
    """
    Converte um arquivo XML no formato especificado para um dicionário
    
    Args:
        xml_file_path (str): Caminho para o arquivo XML
    
    Returns:
        list: Lista de dicionários no formato especificado
    """
    counter = 0
    result = []
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    
    for si_element in root.findall('ns:si', namespace):
        r_elements = si_element.findall('ns:r', namespace)
        texto = None

        if r_elements:
            partes = []
            for r in r_elements:
                t = r.find('ns:t', namespace)
                if t is not None and t.text is not None:
                    partes.append(t.text)
            if partes:
                texto = ''.join(partes).strip()
        else:
            t = si_element.find('ns:t', namespace)
            if t is not None and t.text is not None:
                texto = t.text.strip()

        if texto is not None:
            result.append({str(counter): texto})
            counter += 1

    try:
        with open('temp/resultadox.json', 'w', encoding='utf-8') as f:
            dump(result, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro inesperado: {e}")

# if __name__ == '__main__':
#     xml_sharedstring = Path("temp/xl/sharedStrings.xml")
#     xml_para_dict(xml_sharedstring)
