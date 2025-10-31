import pdfplumber
import re
import json

PDF_PATH = "balancete-1.pdf"

def parse_value(text):
    """Converte string monetária brasileira em float (ex: '1.234,56' -> 1234.56)."""
    if text is None:
        return None
    text = text.strip()
    # Remove quaisquer caracteres que não sejam dígitos, pontos ou vírgulas
    text = re.sub(r"[^\d\.,-]", "", text)
    # Trata números negativos com parênteses ou sinais
    text = text.replace('(', '-').replace(')', '')
    text = text.replace('.', '').replace(',', '.')
    try:
        return float(text)
    except Exception:
        return None

def limpar_descricao(texto):
    """Limpa uma descrição possivelmente 'grudada' de ruídos (dígitos fora de lugar e pontos sobrando)."""
    if texto is None:
        return ""
    s = texto.strip()
    # Replace underscores/tabs/multiple spaces with single space
    s = re.sub(r"[_\t]+", " ", s)
    # Remove dígitos soltos que apareceram no OCR dentro das palavras (ex: CIRCU2L1A -> CIRCULA)
    # Mas mantenha números isolados (possíveis códigos) — aqui assumimos que códigos já foram extraídos.
    s = re.sub(r"(?<=\D)\d+(?=\D)", "", s)  # dígitos entre letras
    s = s.replace(".", " ")  # pontos dentro da descrição viram espaços
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def extrair_quatro_valores_finais(linha):
    """
    Tenta extrair os 4 valores monetários no fim da linha.
    Retorna (saldo_anterior, debito, credito, saldo_atual, resto_da_linha) ou (None...).
    """
    # captura quatro números possivelmente com pontos e vírgulas, possivelmente separados por espaços
    m = re.search(r"([\d\.,\(\)-]+)\s+([\d\.,\(\)-]+)\s+([\d\.,\(\)-]+)\s+([\d\.,\(\)-]+)\s*$", linha)
    if not m:
        return None
    s_anterior, deb, cred, s_atual = m.groups()
    resto = linha[:m.start()].strip()
    return (s_anterior, deb, cred, s_atual, resto)

def extrair_classificacao(resto):
    """Encontra a classificação tipo 1.1.01.01 dentro do texto restante."""
    m = re.search(r"(\b\d+(?:\.\d+)+\b)", resto)
    if m:
        return m.group(1)
    return None

def extrair_codigo(resto, classificacao):
    """
    Tenta pegar o código (número inteiro) do início ou próximo à classificação.
    Se não houver token puro, tenta separar dígitos colados no início/fim de uma palavra (ex: CAIXA4).
    """

    print(resto)
    print(resto.split())
    print('-'*50)






    # Primeiro, procure por número isolado
    tokens = re.findall(r"\b\d+\b", resto)
    if tokens:
        return tokens[0]
    # Se não, procure por palavra que termina com dígitos (ex: 'CAIXA4')
    m = re.search(r"\b([^\s\d]+)(\d+)\b", resto)
    if m:
        # retorna só os dígitos encontrados
        return m.group(2)
    # se ainda nada, pode haver código integrado na própria classificação (raro)
    if classificacao:
        # às vezes a classificação tem prefixo incompleto; não forçamos aqui
        return None
    return None

def extrair_descricao(resto, codigo, classificacao):
    """
    Gera a descrição removendo o que já foi identificado (código, classificação).
    Depois limpa ruídos (dígitos dentro de palavras, pontos excessivos).
    """
    s = resto
    if codigo:
        # remove primeira ocorrência do código
        s = re.sub(r"\b" + re.escape(str(codigo)) + r"\b", "", s, count=1)
    if classificacao:
        s = s.replace(classificacao, "")
    # Trim e limpeza
    s = limpar_descricao(s)
    return s or None

def extrair_dados_linha(texto):
    """
    Tenta extrair os campos com o padrão estrito; se falhar usa extração robusta.
    Campos esperados: codigo, classificacao, descricao, saldo_anterior, debito, credito, saldo_atual
    """
    texto = texto.strip()
    # Primeiro, tentativa rígida (quando tudo está bem separado)
    padrao_rigido = (
        r"^(?P<codigo>\d+)\s+(?P<classificacao>[\d\.]+)\s+"
        r"(?P<descricao>.+?)\s+"
        r"(?P<saldo_anterior>[\d\.,\(\)-]+)\s+"
        r"(?P<debito>[\d\.,\(\)-]+)\s+"
        r"(?P<credito>[\d\.,\(\)-]+)\s+"
        r"(?P<saldo_atual>[\d\.,\(\)-]+)$"
    )
    m = re.match(padrao_rigido, texto)
    if m:
        return {
            "codigo": m.group("codigo"),
            "classificacao": m.group("classificacao"),
            "descricao": limpar_descricao(m.group("descricao")),
            "saldo_anterior": parse_value(m.group("saldo_anterior")),
            "debito": parse_value(m.group("debito")),
            "credito": parse_value(m.group("credito")),
            "saldo_atual": parse_value(m.group("saldo_atual")),
        }

    # Se padrão rígido falhou, tenta extrair os 4 valores finais (estratégia robusta)
    quad = extrair_quatro_valores_finais(texto)
    if not quad:
        return None
    s_anterior, deb, cred, s_atual, resto = quad

    classificacao = extrair_classificacao(resto)
    codigo = extrair_codigo(resto, classificacao)
    descricao = extrair_descricao(resto, codigo, classificacao)

    return {
        "codigo": codigo,
        "classificacao": classificacao,
        "descricao": descricao,
        "saldo_anterior": parse_value(s_anterior),
        "debito": parse_value(deb),
        "credito": parse_value(cred),
        "saldo_atual": parse_value(s_atual),
    }

def identificar_nivel(linha):
    """Identifica o nível de indentação com base no número de pontos na classificação."""
    classificacao = linha.get('classificacao')
    if not classificacao:
        return 0
    return classificacao.count('.')

def ler_balancete(pdf_path):
    dados = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            for linha in texto.split('\n'):
                if not linha.strip():
                    continue
                dado = extrair_dados_linha(linha)
                if dado:
                    dado["nivel"] = identificar_nivel(dado)
                    dados.append(dado)
                else:
                    # opcional: log para depuração de linhas que ainda falharam
                    # print("Linha ignorada:", linha)
                    pass
    return dados

def montar_hierarquia(dados):
    """
    Monta estrutura hierárquica com base nos níveis de classificação.
    """
    raiz = []
    pilha = [(-1, raiz)]

    for item in dados:
        nivel = item.get("nivel", 0)
        # se classificacao é None mas descricao existe, podemos tentar inferir nível pelo formato do código (se houver)
        while pilha and pilha[-1][0] >= nivel:
            pilha.pop()
        novo = {**item, "filhos": []}
        pilha[-1][1].append(novo)
        pilha.append((nivel, novo["filhos"]))

    return raiz

if __name__ == "__main__":
    dados = ler_balancete(PDF_PATH)
    estrutura = montar_hierarquia(dados)
    # print(json.dumps(estrutura, indent=2, ensure_ascii=False))
