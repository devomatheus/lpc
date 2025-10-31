#!/usr/bin/env python3
import pdfplumber
import json
import re

def extrair_tabela_pdf(pdf_path):
    """
    Extrai dados de tabela do PDF e retorna em formato JSON.
    """
    dados = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                # Tenta extrair tabelas
                tabelas = pagina.extract_tables()
                
                if tabelas:
                    for idx_tabela, tabela in enumerate(tabelas):
                        for idx_linha, linha in enumerate(tabela):
                            if linha and any(cell for cell in linha if cell):
                                # Remove valores None e limpa espaços
                                linha_limpa = [cell.strip() if cell else "" for cell in linha]
                                dados.append({
                                    "pagina": num_pagina,
                                    "tabela": idx_tabela + 1,
                                    "linha": idx_linha + 1,
                                    "dados": linha_limpa
                                })
                else:
                    # Se não encontrar tabelas, tenta extrair texto estruturado
                    texto = pagina.extract_text()
                    if texto:
                        linhas = texto.split('\n')
                        for idx, linha in enumerate(linhas):
                            if linha.strip():
                                dados.append({
                                    "pagina": num_pagina,
                                    "linha": idx + 1,
                                    "texto": linha.strip()
                                })
    
    except Exception as e:
        return {"erro": str(e)}
    
    return dados

def processar_balancete(dados):
    """
    Processa os dados extraídos e estrutura em formato mais legível.
    """
    if "erro" in dados:
        return dados
    
    # Identifica se há cabeçalho
    resultado = {
        "metadata": {
            "total_linhas": len(dados),
            "paginas": set()
        },
        "cabecalho": [],
        "registros": []
    }
    
    for item in dados:
        if "pagina" in item:
            resultado["metadata"]["paginas"].add(item["pagina"])
        
        # Identifica possível cabeçalho (primeiras linhas ou linhas com palavras-chave)
        if "dados" in item:
            linha_texto = " ".join(item["dados"]).lower()
            if any(palavra in linha_texto for palavra in ["código", "descrição", "saldo", "débito", "crédito"]):
                resultado["cabecalho"].append(item)
            else:
                resultado["registros"].append(item)
        elif "texto" in item:
            resultado["registros"].append(item)
    
    resultado["metadata"]["paginas"] = sorted(list(resultado["metadata"]["paginas"]))
    
    return resultado

def main():
    pdf_path = "balancete-f3.pdf"
    
    print(f"Extraindo dados de {pdf_path}...")
    dados = extrair_tabela_pdf(pdf_path)
    
    print("Processando dados...")
    resultado = processar_balancete(dados)
    
    # Salva em arquivo JSON
    output_file = "balancete-f3.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\nDados extraídos e salvos em: {output_file}")
    print(f"\nTotal de registros: {resultado['metadata']['total_linhas']}")
    print(f"Páginas processadas: {resultado['metadata']['paginas']}")
    
    # Exibe preview dos primeiros registros
    print("\n--- Preview dos primeiros registros ---")
    for i, registro in enumerate(resultado['registros'][:5]):
        print(f"\nRegistro {i+1}:")
        print(json.dumps(registro, ensure_ascii=False, indent=2))
    
    return resultado

if __name__ == "__main__":
    resultado = main()
