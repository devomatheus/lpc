from werkzeug.datastructures import FileStorage
from PyPDF2 import PdfReader
from pathlib import Path
from io import BytesIO


def read_periods_from_pdf(origem_pdf):
    """
    Lê a primeira página de um PDF e retorna o texto extraído.

    A origem do PDF pode ser o caminho para um arquivo, um FileStorage
    recebido via requisição Flask ou qualquer objeto compatível com arquivo.
    """
    try:
        if isinstance(origem_pdf, (str, Path)):
            caminho = Path(origem_pdf)

            if not caminho.exists():
                raise FileNotFoundError(f"Arquivo '{origem_pdf}' não encontrado.")

            with caminho.open("rb") as arquivo:
                return _extrair_texto(arquivo)

        stream = _obter_stream(origem_pdf)
        return _extrair_texto(stream)

    except Exception as exc:
        raise ValueError(f"Erro ao ler o PDF: {str(exc)}") from exc


def _obter_stream(origem_pdf):
    if origem_pdf is None:
        raise ValueError("Nenhum arquivo PDF fornecido.")

    if isinstance(origem_pdf, FileStorage):
        origem_pdf.stream.seek(0)
        # Copia o conteúdo do stream para BytesIO para garantir compatibilidade
        # entre Windows e Linux, especialmente com PyPDF2
        conteudo = origem_pdf.stream.read()
        return BytesIO(conteudo)

    if hasattr(origem_pdf, "seek") and hasattr(origem_pdf, "read"):
        origem_pdf.seek(0)
        # Se já for um BytesIO ou similar, retorna diretamente
        if isinstance(origem_pdf, BytesIO):
            return origem_pdf
        # Caso contrário, copia para BytesIO para garantir compatibilidade
        conteudo = origem_pdf.read()
        return BytesIO(conteudo)

    raise TypeError("Origem do PDF inválida.")


def _extrair_texto(stream):
    leitor_pdf = PdfReader(stream)

    if len(leitor_pdf.pages) == 0:
        raise ValueError("PDF não contém páginas.")

    primeira_pagina = leitor_pdf.pages[0]
    texto = primeira_pagina.extract_text()

    if not texto:
        raise ValueError("Não foi possível extrair texto do PDF.")

    return texto
