#!/usr/bin/env python3
import pdfplumber
import json
import re

def remover_espacos_letras(texto):
    """
    Remove espaços entre letras individuais.
    Exemplo: 'A T I V O' -> 'ATIVO'
    """
    if not texto:
        return ""
    
    # Remove espaços que estão entre letras/números únicos
    resultado = re.sub(r'\b([A-Z0-9])\s+(?=[A-Z0-9]\b)', r'\1', texto)
    return resultado.strip()

def extrair_valores_monetarios(texto):
    """
    Extrai valores monetários de um texto.
    Retorna lista de valores encontrados.
    """
    # Padrão para valores: números com pontos e vírgulas, e possivelmente parênteses
    pattern = r'(\(?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*\)?)'
    valores = re.findall(pattern, texto)
    return [v.strip() for v in valores if v.strip()]

def processar_linha_balancete(linha_cells):
    """
    Processa uma linha da tabela do balancete.
    """
    if not linha_cells or len(linha_cells) < 5:
        return None
    
    # Remove células vazias do final
    linha_cells = [c if c else "" for c in linha_cells]
    
    # Junta todas as células em um texto único para análise
    texto_completo = " ".join(linha_cells)
    
    # Pula se for cabeçalho ou linha vazia
    if not texto_completo.strip():
        return None
    if any(palavra in texto_completo for palavra in ['Conta S', 'Classificação', 'Saldo Ant', 'Balancete', 'CNPJ']):
        return None
    
    # Tenta identificar os campos
    conta = ""
    status = ""
    classificacao = ""
    descricao = ""
    
    # Procura por conta (número pequeno no início)
    match_conta = re.search(r'^\s*(\d{1,4})\s+', texto_completo)
    if match_conta:
        conta = match_conta.group(1)
    
    # Procura por status (S ou A)
    match_status = re.search(r'\b([SA])\b', texto_completo)
    if match_status:
        status = match_status.group(1)
    
    # Procura por classificação (formato x.x.x ou x)
    match_class = re.search(r'\b(\d+(?:\.\d+)+)\b', texto_completo)
    if match_class:
        classificacao = match_class.group(1)
    elif conta:
        # Se não encontrou classificação detalhada, usa a conta
        classificacao = conta
    
    # Extrai valores monetários
    valores = extrair_valores_monetarios(texto_completo)
    
    # Remove números que são parte da classificação/conta dos valores
    valores_filtrados = []
    for v in valores:
        # Só adiciona se tiver vírgula (indicando valor decimal)
        if ',' in v:
            valores_filtrados.append(v)
    
    # Extrai descrição (texto entre classificação e valores)
    # Remove conta, status, classificação e valores do texto
    descricao_temp = texto_completo
    if conta:
        descricao_temp = descricao_temp.replace(conta, '', 1)
    if status:
        descricao_temp = descricao_temp.replace(status, '', 1)
    if classificacao:
        descricao_temp = descricao_temp.replace(classificacao, '', 1)
    
    # Remove valores do texto da descrição
    for valor in valores_filtrados:
        descricao_temp = descricao_temp.replace(valor, '')
    
    # Limpa e remove espaços entre letras
    descricao = remover_espacos_letras(descricao_temp)
    # Remove espaços múltiplos e caracteres especiais desnecessários
    descricao = re.sub(r'\s+', ' ', descricao).strip()
    
    # Atribui valores
    saldo_anterior = valores_filtrados[0] if len(valores_filtrados) > 0 else ""
    debito = valores_filtrados[1] if len(valores_filtrados) > 1 else ""
    credito = valores_filtrados[2] if len(valores_filtrados) > 2 else ""
    saldo = valores_filtrados[3] if len(valores_filtrados) > 3 else ""
    
    # Só retorna se tiver informação relevante
    if classificacao or descricao or any(valores_filtrados):
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

def extrair_balancete(pdf_path):
    """
    Extrai dados do balancete PDF.
    """
    registros = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                print(f"Processando página {num_pagina}...")
                
                # Extrai tabelas
                tabelas = pagina.extract_tables()
                
                for tabela in tabelas:
                    for linha in tabela:
                        registro = processar_linha_balancete(linha)
                        if registro:
                            registro["pagina"] = num_pagina
                            registros.append(registro)
    
    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        import traceback
        traceback.print_exc()
        return {"erro": str(e)}
    
    return {
        "metadata": {
            "arquivo": pdf_path,
            "total_registros": len(registros),
            "descricao": "Balancete Societário - Período: 01/07/2024 a 31/07/2024"
        },
        "registros": registros
    }

def main():
    pdf_path = "balancete-f3.pdf"
    
    print(f"\n{'='*80}")
    print(f"EXTRAÇÃO DE BALANCETE - PDF PARA JSON")
    print(f"{'='*80}\n")
    
    resultado = extrair_balancete(pdf_path)
    
    if "erro" in resultado:
        print(f"\n❌ Erro: {resultado['erro']}")
        return
    
    # Salva arquivo JSON
    output_file = "balancete-f3-dados.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Extração concluída!")
    print(f"✓ Total de registros: {resultado['metadata']['total_registros']}")
    print(f"✓ Arquivo salvo: {output_file}\n")
    
    # Preview
    print(f"{'='*80}")
    print(f"PREVIEW - PRIMEIROS 20 REGISTROS")
    print(f"{'='*80}\n")
    
    for i, reg in enumerate(resultado['registros'][:20], 1):
        print(f"[{i}] Conta: {reg['conta']:>4} | Status: {reg['status']} | Pág: {reg['pagina']}")
        print(f"    Classificação: {reg['classificacao']}")
        print(f"    Descrição: {reg['descricao'][:60]}...")  # Limita a 60 chars
        print(f"    Saldo Anterior: {reg['saldo_anterior']:>20}")
        print(f"    Débito........: {reg['debito']:>20}")
        print(f"    Crédito.......: {reg['credito']:>20}")
        print(f"    Saldo.........: {reg['saldo']:>20}")
        print()
    
    if len(resultado['registros']) > 20:
        print(f"... e mais {len(resultado['registros']) - 20} registros no arquivo JSON.\n")
    
    print(f"{'='*80}\n")
    
    return resultado

if __name__ == "__main__":
    resultado = main()
