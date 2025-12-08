#!/usr/bin/env python3
"""Extrai o balancete em JSON estruturado a partir do PDF original."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pdfplumber

PDF_PATH = Path("parser-pdf/balancete.pdf")
OUTPUT_PATH = Path("balancete.json")
MIN_TOP = 70.0
ROW_TOLERANCE = 1.5

CODE_PATTERN = re.compile(r"^\d{1,6}$")
CLASS_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")
NUMERIC_PATTERN = re.compile(r"^[\d.,()\-]+(?:[DC])?$")
UNDERSCORE_PATTERN = re.compile(r"^_+$")
WHITESPACE_PATTERN = re.compile(r"\s+")

COLUMN_NAMES = [
    "code",
    "classification",
    "account",
    "previous_balance",
    "debit",
    "credit",
    "current_balance",
]


def clean_text(value: Optional[str]) -> Optional[str]:
    """Remove espaços duplicados e normaliza strings nulas."""
    if value is None:
        return None
    value = WHITESPACE_PATTERN.sub(" ", value).strip()
    return value or None


def parse_header(page: pdfplumber.page.Page) -> Dict[str, Optional[str]]:
    text = page.extract_text(layout=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    separator = re.compile(r"\s{2,}")

    def extract_after(label: str) -> Optional[str]:
        pattern = re.compile(rf"{re.escape(label)}\s*(\S.*?)(?:(?:\s{{2,}})|$)")
        for idx, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                return match.group(1).strip()
            if label in line:
                remainder = line.split(label, 1)[1].strip()
                if remainder:
                    return remainder
                if idx + 1 < len(lines):
                    return lines[idx + 1].strip()
        return None

    def left_segment(value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        return separator.split(value, maxsplit=1)[0].strip()

    report_line = left_segment(next((ln for ln in lines if ln.strip() == "BALANCETE"), None))
    consolidated_line = left_segment(next((ln for ln in lines if "CONSOLIDADO" in ln), None))
    report_type_parts = [part for part in (report_line, consolidated_line) if part]
    report_type = " ".join(report_type_parts) if report_type_parts else None

    return {
        "company": extract_after("Empresa:"),
        "cnpj": extract_after("C.N.P.J.:") ,
        "report_type": report_type,
        "period": extract_after("Período:"),
        "issue_date": extract_after("Emissão:"),
        "time": extract_after("Hora:"),
        "page": extract_after("Folha:"),
        "book_number": extract_after("Número livro:"),
    }


def detect_column(word: Dict[str, float], text: str) -> Optional[str]:
    center = (word["x0"] + word["x1"]) / 2
    if word["x1"] <= 30 and CODE_PATTERN.fullmatch(text):
        return "code"
    if center <= 120 and CLASS_PATTERN.fullmatch(text):
        return "classification"
    if center <= 320 and word["x0"] >= 95:
        return "account"
    if NUMERIC_PATTERN.fullmatch(text):
        if center <= 410:
            return "previous_balance"
        if center <= 460:
            return "debit"
        if center <= 520:
            return "credit"
        if center > 320:
            return "current_balance"
    return None


def group_rows(words: List[Dict[str, float]]) -> List[List[Dict[str, float]]]:
    rows: List[List[Dict[str, float]]] = []
    current: List[Dict[str, float]] = []
    current_top: Optional[float] = None
    for word in words:
        if current and current_top is not None and abs(word["top"] - current_top) > ROW_TOLERANCE:
            rows.append(current)
            current = []
        current.append(word)
        if current_top is None or abs(word["top"] - current_top) > ROW_TOLERANCE:
            current_top = word["top"]
    if current:
        rows.append(current)
    return rows


def parse_row(row_words: List[Dict[str, float]]) -> Optional[Dict[str, Optional[str]]]:
    buckets: Dict[str, List[str]] = {name: [] for name in COLUMN_NAMES}
    fallback: List[str] = []
    for word in sorted(row_words, key=lambda item: item["x0"]):
        text = word["text"].strip()
        if not text:
            continue
        column = detect_column(word, text)
        if column:
            buckets[column].append(text)
        elif not CODE_PATTERN.fullmatch(text) and not CLASS_PATTERN.fullmatch(text):
            fallback.append(text)
    if not buckets["account"] and fallback:
        alt_account = [frag for frag in fallback if not UNDERSCORE_PATTERN.fullmatch(frag)]
        if alt_account:
            buckets["account"] = alt_account
    cleaned = {col: clean_text(" ".join(values)) for col, values in buckets.items() if values}
    for col in COLUMN_NAMES:
        cleaned.setdefault(col, None)
    if cleaned["account"] == "Descrição da conta":
        return None
    if cleaned["account"] and UNDERSCORE_PATTERN.fullmatch(cleaned["account"]):
        return None
    if not any(cleaned.values()):
        return None
    return cleaned


def extract_rows(page: pdfplumber.page.Page) -> List[Dict[str, Optional[str]]]:
    words = [
        word
        for word in page.extract_words(use_text_flow=True, keep_blank_chars=True)
        if word["top"] >= MIN_TOP
    ]
    words.sort(key=lambda item: (item["top"], item["x0"]))
    rows = group_rows(words)
    parsed_rows: List[Dict[str, Optional[str]]] = []
    for row_words in rows:
        parsed = parse_row(row_words)
        if parsed:
            parsed_rows.append(parsed)
    return parsed_rows


def classification_variants(classification: str) -> Iterable[str]:
    parts = classification.split(".")
    if not parts:
        return []
    variants = {".".join(parts)}
    last = parts[-1]
    trimmed = last
    while len(trimmed) > 1 and trimmed.endswith("0"):
        trimmed = trimmed[:-1]
        variants.add(".".join([*parts[:-1], trimmed]))
    if trimmed != last and trimmed.lstrip("0"):
        variants.add(".".join([*parts[:-1], trimmed.lstrip("0")]))
    if last.lstrip("0") and last.lstrip("0") != last:
        variants.add(".".join([*parts[:-1], last.lstrip("0")]))
    return variants


def attach_parents(rows: List[Dict[str, Optional[str]]]) -> None:
    lookup: Dict[str, str] = {}
    for row in rows:
        cls = row.get("classification")
        account = row.get("account")
        if not cls or not account:
            continue
        for variant in classification_variants(cls):
            lookup.setdefault(variant, account)
    for row in rows:
        cls = row.get("classification")
        parent: Optional[str] = None
        if cls:
            parts = cls.split(".")
            while len(parts) > 1 and not parent:
                parts = parts[:-1]
                for variant in classification_variants(".".join(parts)):
                    if variant in lookup:
                        parent = lookup[variant]
                        break
        row["parent_category"] = parent


def extract_data() -> Dict[str, object]:
    with pdfplumber.open(PDF_PATH) as pdf:
        header = parse_header(pdf.pages[0])
        data_rows: List[Dict[str, Optional[str]]] = []
        for page in pdf.pages:
            data_rows.extend(extract_rows(page))
    attach_parents(data_rows)
    return {"header": header, "data": data_rows}


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {PDF_PATH}")
    payload = extract_data()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()
