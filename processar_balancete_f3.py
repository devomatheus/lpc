#!/usr/bin/env python3
import pdfplumber
import json
import re

def limpar_valor(texto):
    """Remove espaços e formata valores numéricos."""
    if not texto:
        return ""
    # Remove espaços entre dígitos
    texto = re.sub(r'\s+', '', texto)
    return texto

def processar_linha_tabela(linha):
    """
    Processa uma linha da tabela e extrai os campos estruturados.
    """
    if not linha or len(linha) < 6:
        return None
    
    # Remove elementos vazios do início
    linha_limpa = [cell.strip() if cell else "" for cell in linha]
    
    # Tenta identificar os campos
    conta = ""
    status = ""
    classificacao = ""
    descricao = ""
    saldo_anterior = ""
    debito = ""
    credito = ""
    saldo = ""
    
    # A estrutura parece ser:
    # [info geral], conta, vazio, status, vazio, classificação+descrição, saldo_ant, vazio, vazio, debito, vazio, credito, vazio, saldo, vazio, vazio
    
    try:
        # Procura por padrões de conta (números)
        for i, cell in enumerate(linha_limpa):
            if cell and cell.isdigit() and len(cell) <= 3:
                conta = cell
                break
        
        # Procura por status (S ou A)
        for i, cell in enumerate(linha_limpa):
            if cell in ['S', 'A']:
                status = cell
                break
        
        # Procura por classificação e descrição (formato: "1.1.01 DESCRIÇÃO")
        for i, cell in enumerate(linha_limpa):
            if cell and re.match(r'^\d+\.', cell):
                # Separa classificação e descrição
                partes = cell.split(maxsplit=1)
                if len(partes) >= 1:
                    classificacao = limpar_valor(partes[0])
                if len(partes) >= 2:
                    descricao = partes[1]
                break
        
        # Procura por valores monetários (contêm vírgulas, pontos e parênteses)
        valores = []
        for i, cell in enumerate(linha_limpa):
            # Verifica se é um valor monetário
            if cell and (re.search(r'[\d,\.]', cell) or '(' in cell or ')' in cell):
                # Ignora se for apenas números sem formatação (provavelmente conta)
                if not (cell.isdigit() and len(cell) <= 3):
                    valores.append(limpar_valor(cell))
        
        # Atribui valores na ordem: saldo_anterior, debito, credito, saldo
        if len(valores) >= 1:
            saldo_anterior = valores[0]
        if len(valores) >= 2:
            debito = valores[1]
        if len(valores) >= 3:
            credito = valores[2]
        if len(valores) >= 4:
            saldo = valores[3]
    
    except Exception as e:
        print(f"Erro ao processar linha: {e}")
        return None
    
    # Retorna apenas se houver informação relevante
    if classificacao or descricao or any([saldo_anterior, debito, credito, saldo]):
        return {
            "conta": conta,
            "status": status,
            "classificacao": classificacao,
            "descricao": descricao,
            "saldo_anterior": saldo_anterior,
            "debito": debito,
            "credito": credito,
            "saldo": saldo
        }
    
    return None

def extrair_balancete_estruturado(pdf_path):
    """
    Extrai dados estruturados do balancete.
    """
    registros = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                print(f"Processando página {num_pagina}...")
                
                # Extrai tabelas
                tabelas = pagina.extract_tables()
                
                for idx_tabela, tabela in enumerate(tabelas):
                    for idx_linha, linha in enumerate(tabela):
                        # Pula linhas de cabeçalho
                        linha_texto = " ".join([str(c) for c in linha if c]).lower()
                        if "saldo ant" in linha_texto or "débito" in linha_texto or "crédito" in linha_texto:
                            continue
                        
                        # Processa a linha
                        registro = processar_linha_tabela(linha)
                        if registro:
                            registro["pagina"] = num_pagina
                            registro["tabela"] = idx_tabela + 1
                            registros.append(registro)
    
    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        return {"erro": str(e)}
    
    return {
        "metadata": {
            "arquivo": pdf_path,
            "total_registros": len(registros)
        },
        "registros": registros
    }

def main():
    pdf_path = "balancete-f3.pdf"
    
    print(f"\nExtraindo dados estruturados de {pdf_path}...\n")
    resultado = extrair_balancete_estruturado(pdf_path)
    
    if "erro" in resultado:
        print(f"Erro: {resultado['erro']}")
        return
    
    # Salva em arquivo JSON
    output_file = "balancete-f3-estruturado.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Dados extraídos e salvos em: {output_file}")
    print(f"✓ Total de registros: {resultado['metadata']['total_registros']}")
    
    # Exibe preview dos primeiros 10 registros
    print("\n" + "="*80)
    print("PREVIEW DOS PRIMEIROS 10 REGISTROS")
    print("="*80)
    
    for i, registro in enumerate(resultado['registros'][:10]):
        print(f"\n[{i+1}] Página {registro['pagina']}")
        print(f"    Conta: {registro['conta']}")
        print(f"    Status: {registro['status']}")
        print(f"    Classificação: {registro['classificacao']}")
        print(f"    Descrição: {registro['descricao']}")
        print(f"    Saldo Anterior: {registro['saldo_anterior']}")
        print(f"    Débito: {registro['debito']}")
        print(f"    Crédito: {registro['credito']}")
        print(f"    Saldo: {registro['saldo']}")
    
    print("\n" + "="*80)
    print(f"Arquivo completo salvo em: {output_file}")
    print("="*80 + "\n")
    
    return resultado

if __name__ == "__main__":
    resultado = main()
