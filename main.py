import pdfplumber
import re
import json

# Caminho do arquivo PDF
PDF_PATH = "balancete-1.pdf"

def parse_value(text):
    """Converte string monetária brasileira em float."""
    text = text.replace('.', '').replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None

def identificar_nivel(linha):
    """Identifica o nível de indentação com base no número de pontos na classificação."""
    classificacao = linha.get('classificacao')
    if not classificacao:
        return 0
    return classificacao.count('.')

def extrair_dados_linha(texto):
    """
    Recebe uma linha de texto bruta e tenta separar os campos:
    Código, Classificação, Descrição, Saldo Anterior, Débito, Crédito, Saldo Atual.
    """
    padrao = (
        r"^(?P<codigo>\d+)\s+(?P<classificacao>[\d\.]+)\s+"
        r"(?P<descricao>.+?)\s+"
        r"(?P<saldo_anterior>[\d\.,]+)\s+"
        r"(?P<debito>[\d\.,]+)\s+"
        r"(?P<credito>[\d\.,]+)\s+"
        r"(?P<saldo_atual>[\d\.,]+)$"
    )

    m = re.match(padrao, texto.strip())
    if not m:
        return None

    return {
        "codigo": m.group("codigo"),
        "classificacao": m.group("classificacao"),
        "descricao": m.group("descricao").strip(),
        "saldo_anterior": parse_value(m.group("saldo_anterior")),
        "debito": parse_value(m.group("debito")),
        "credito": parse_value(m.group("credito")),
        "saldo_atual": parse_value(m.group("saldo_atual")),
    }

def ler_balancete(pdf_path):
    dados = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            # print(type(texto))
            # print(texto)
            # print('-'*50)
            if not texto:
                continue
            for linha in texto.split('\n'):
                print(linha)
                print('-'*50)
                dado = extrair_dados_linha(linha)
                if dado:
                    dado["nivel"] = identificar_nivel(dado)
                    dados.append(dado)
    return dados

def montar_hierarquia(dados):
    """
    Monta estrutura hierárquica com base nos níveis de classificação.
    Exemplo:
    ATIVO -> CIRCULANTE -> DISPONIBILIDADES -> CAIXA -> FUNDO FIXO
    """
    raiz = []
    pilha = [(-1, raiz)]

    for item in dados:
        nivel = item["nivel"]
        while pilha and pilha[-1][0] >= nivel:
            pilha.pop()
        novo = {**item, "filhos": []}
        pilha[-1][1].append(novo)
        pilha.append((nivel, novo["filhos"]))

    return raiz

if __name__ == "__main__":
    dados = ler_balancete(PDF_PATH)
    estrutura = montar_hierarquia(dados)

    # Exibe de forma legível
    print(json.dumps(estrutura, indent=2, ensure_ascii=False))
