from __future__ import annotations

from typing import Iterable, List, Optional, Tuple
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from json import load
from json import dump


caminho = 'temp/resultado.json'

with open(caminho, 'r', encoding='utf-8') as f:
    resultado = load(f)


NS = {"ss": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def reverter_formato_excel(numero_excel):
    """
    Reverte a conversão automática do Excel
    De: 36892.000000
    Para: 1.1.01 (formato original)
    """
    try:
        base_date = datetime(1899, 12, 30)
        
        data = base_date + timedelta(days=float(numero_excel))
        
        dia = data.day
        mes = data.month
        ano = data.year % 100
        
        return f"{dia}.{mes}.{ano:02d}"
        
    except Exception as e:
        return f"Erro: {e}"


def resolve_resultado(index_str: str) -> Optional[str]:
    """Dado o índice em formato string (v), retorna o valor correspondente em `resultado`.
    `resultado` é uma lista de dicionários com uma única chave string (o índice).
    """
    try:
        idx = int(index_str)
    except (TypeError, ValueError):
        return None
    if not isinstance(resultado, list):
        return None
    if idx < 0 or idx >= len(resultado):
        return None
    entry = resultado[idx]
    if not isinstance(entry, dict):
        return None
    return entry.get(str(idx))


def _tem_segmento_maior_que_3(valor: str) -> bool:
    if not isinstance(valor, str):
        return False
    partes = valor.split('.')
    for p in partes:
        if p.isdigit() and len(p) > 3:
            return True
    return False


def update_cell_value_if_needed(cell: CellData) -> None:
    """Se a célula for das colunas A ou B e tiver um valor com segmento numérico
    > 3 dígitos entre pontos, converte usando reverter_formato_excel.
    """
    addr = cell.address or ''
    col = ''
    i = 0
    while i < len(addr) and addr[i].isalpha():
        col += addr[i]
        i += 1
    col = col.upper()

    if col in ('A', 'B') and cell.cell_type is None and cell.value is not None:
        v = str(cell.value).strip()
        if _tem_segmento_maior_que_3(v):
            cell.value = reverter_formato_excel(v)


def get_cell_by_address(row: RowData, address: str) -> Optional[CellData]:
    for c in row.cells:
        if c.address == address:
            return c
    return None


def build_row_values(row: RowData) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Constroi a lista das 8 colunas (A..H) da linha.
    Retorna lista de tuplas (address, cell_type, raw_or_mapped_value_str).
    - Para t="s": mapeia via `resultado` usando `v`.
    - Para demais tipos: retorna o conteudo de <v> (string) se existir; caso contrario None.
    """
    cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
    out = []
    for col in cols:
        addr = f"{col}{row.row_number}"
        cell = get_cell_by_address(row, addr)
        if cell is None:
            out.append((addr, None, None))
            continue
        update_cell_value_if_needed(cell)
        if cell.cell_type == 's' and cell.value is not None:
            mapped = resolve_resultado(cell.value)
            out.append((addr, cell.cell_type, mapped))
        else:
            out.append((addr, cell.cell_type, cell.value))
    return out


def parse_address(addr: str) -> Tuple[str, int]:
    i = 0
    while i < len(addr) and addr[i].isalpha():
        i += 1
    col = addr[:i].upper()
    row = int(addr[i:]) if i < len(addr) else 0
    return col, row


def montar_json_duas_listas(
    lista1: List[Tuple[str, object]],
    lista2: List[Tuple[str, object]],
) -> List[dict]:
    """Une duas listas de (address, valor) em JSON por linha, A..H, ordem crescente.
    - Prioriza valor não-nulo da lista1; se ausente/nulo, usa da lista2.
    - Gera objetos por linha: {'a1': v, 'b1': v, ..., 'h1': v} ...
    """

    combined: dict[str, object] = {}

    def apply(lst: List[Tuple[str, object]], prefer: bool) -> None:
        for addr, val in lst:
            if not addr:
                continue
            key = addr.lower()
            if prefer:
                if key not in combined or combined[key] is None:
                    combined[key] = val
            else:
                if key not in combined or combined[key] is None:
                    combined[key] = val

    apply(lista1, prefer=True)
    apply(lista2, prefer=False)

    rows_present: set[int] = set()
    for key in combined.keys():
        _, r = parse_address(key)
        if r:
            rows_present.add(r)

    if not rows_present:
        rows = list(range(1, 78))
    else:
        rows = sorted(rows_present)

    cols_order = ["A", "B", "C", "D", "E", "F", "G", "H"]
    json_rows: List[dict] = []
    for r in rows:
        obj: dict = {}
        for c in cols_order:
            key = f"{c}{r}".lower()
            obj[key] = combined.get(key)
        json_rows.append(obj)
    return json_rows


@dataclass
class CellData:
    address: str
    style: Optional[str]
    cell_type: Optional[str]
    value: Optional[str]


@dataclass
class RowData:
    row_number: int
    spans: Optional[str]
    height: Optional[str]
    custom_height: Optional[str]
    cells: List[CellData]


@dataclass
class MergeRange:
    start_col: int
    start_row: int
    end_col: int
    end_row: int

    def contains_row(self, row_number: int) -> bool:
        return self.start_row <= row_number <= self.end_row


def col_letters_to_index(col_letters: str) -> int:
    """Converte letras de coluna (ex: 'A', 'H', 'AA') para índice 1-based."""
    result = 0
    for ch in col_letters:
        result = result * 26 + (ord(ch.upper()) - ord("A") + 1)
    return result


def parse_cell_ref(ref: str) -> Tuple[int, int]:
    """Converte referência de célula (ex: 'C12') para (col_index_1based, row_number)."""
    i = 0
    while i < len(ref) and ref[i].isalpha():
        i += 1
    col_part = ref[:i]
    row_part = ref[i:]
    return col_letters_to_index(col_part), int(row_part)


def parse_merge_ref(ref: str) -> MergeRange:
    """Converte um ref de mesclagem 'A1:C3' em MergeRange."""
    start_ref, end_ref = ref.split(":", 1)
    sc, sr = parse_cell_ref(start_ref)
    ec, er = parse_cell_ref(end_ref)
    return MergeRange(start_col=sc, start_row=sr, end_col=ec, end_row=er)


def read_rows(sheet_xml_path: Path) -> List[RowData]:
    tree = ET.parse(sheet_xml_path)
    root = tree.getroot()

    rows: List[RowData] = []
    for row_el in root.findall(".//ss:sheetData/ss:row", NS):
        row_number_str = row_el.get("r") or "0"
        row_number = int(row_number_str)
        spans = row_el.get("spans")
        height = row_el.get("ht")
        custom_height = row_el.get("customHeight")

        cells: List[CellData] = []
        for c in row_el.findall("ss:c", NS):
            address = c.get("r") or ""
            style = c.get("s")
            cell_type = c.get("t")
            v_el = c.find("ss:v", NS)
            value = v_el.text if v_el is not None else None
            cells.append(CellData(address=address, style=style, cell_type=cell_type, value=value))

        rows.append(
            RowData(
                row_number=row_number,
                spans=spans,
                height=height,
                custom_height=custom_height,
                cells=cells,
            )
        )

    return rows


def read_merges(sheet_xml_path: Path) -> List[MergeRange]:
    tree = ET.parse(sheet_xml_path)
    root = tree.getroot()

    merges: List[MergeRange] = []
    for m in root.findall(".//ss:mergeCells/ss:mergeCell", NS):
        ref = m.get("ref")
        if not ref:
            continue
        merges.append(parse_merge_ref(ref))
    return merges


def row_is_merged(row_number: int, merge_ranges: Iterable[MergeRange]) -> bool:
    for mr in merge_ranges:
        if mr.contains_row(row_number):
            return True
    return False


def funcao_A(row: RowData) -> None:
    row_values = build_row_values(row)
    processed: List[Tuple[str, object]] = []
    for addr, ctype, value in row_values:
        if ctype == 's' and isinstance(value, str):
            processed.append((addr, value.split()))
        else:
            processed.append((addr, value))
    return processed


def funcao_B(row: RowData) -> None:
    row_values = build_row_values(row)
    processed: List[Tuple[str, Optional[str]]] = []
    for addr, _, value in row_values:
        processed.append((addr, value))
    return processed


def process_sheet(sheet_xml_path: Path) -> None:
    rows = read_rows(sheet_xml_path)
    merges = read_merges(sheet_xml_path)

    acumulado_A: List[Tuple[str, object]] = []
    acumulado_B: List[Tuple[str, object]] = []

    for row in rows:
        if row_is_merged(row.row_number, merges):
            resultado_com_mesclagem = funcao_A(row)
            if isinstance(resultado_com_mesclagem, list):
                acumulado_A.extend(resultado_com_mesclagem)
        else:
            resultado_sem_mesclagem = funcao_B(row)
            if isinstance(resultado_sem_mesclagem, list):
                acumulado_B.extend(resultado_sem_mesclagem)

    json_final = montar_json_duas_listas(acumulado_A, acumulado_B)
    out_path = sheet_xml_path.parent.parent.parent / "saida.json"
    with open(out_path, "w", encoding="utf-8") as f:
        dump(json_final, f, ensure_ascii=False, indent=2)


def main() -> None:
    project_root = Path(__file__).resolve().parent
    sheet_path = project_root / "temp" / "xl" / "worksheets" / "sheet4.xml"
    process_sheet(sheet_path)


if __name__ == "__main__":
    main()
