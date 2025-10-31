# Este arquivo será o principal

from main8 import xml_para_dict
from main6 import transformar_xlsx_em_zip
from main5 import encontra_arquivo
from pathlib import Path

namespace = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
xml_sharedstring = Path("temp/xl/sharedStrings.xml")

transformar_xlsx_em_zip('balancete-9.xlsx')
xml_para_dict(xml_sharedstring)

pagina_xml = encontra_arquivo()
print(pagina_xml)
