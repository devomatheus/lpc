#!/usr/bin/env python3
import pdfplumber
import json
import re

def extrair_dados_com_texto(pdf_path):
    """
    Extrai dados do PDF usando análise de texto bruto linha por linha.
    """
    registros = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                print(f"Processando página {num_pagina}...")
                
                # Extrai texto bruto
                texto = pagina.extract_text()
                if not texto:
                    continue
                
                linhas = texto.split('\n')
                
                for linha in linhas:
                    linha = linha.strip()
                    
                    # Pula linhas de cabeçalho, título e linhas vazias
                    if not linha or 'JUND TRANSPORTES' in linha or 'CNPJ' in linha:
                        continue
                    if 'Saldo Ant' in linha or 'Débito' in linha or 'Crédito' in linha:
                        continue
                    if 'Balancete' in linha or 'Valores expressos' in linha:
                        continue
                    if linha.startswith('Conta S'):
                        continue
                    
                    # Padrão para linhas de dados:
                    # Número Letra Classificação Descrição Valores...
                    # Exemplo: 1 S 1 A T I V O 11.424.030,31 8.229.271,79 7.363.027,34 12.290.274,76
                    
                    # Tenta extrair: conta, status, resto da linha
                    match = re.match(r'^(\d+)\s+([SA])\s+(.+)$', linha)
                    
                    if match:
                        conta = match.group(1)
                        status = match.group(2)
                        resto = match.group(3)
                        
                        # Extrai classificação e descrição
                        # A classificação tem formato como "1.1.01" ou "1"
                        # A descrição vem depois, com letras espaçadas
                        
                        # Procura por padrão de classificação
                        class_match = re.match(r'^([\d\.]+)\s+(.+)$', resto)
                        
                        if class_match:
                            classificacao = class_match.group(1)
                            resto_linha = class_match.group(2)
                            
                            # Remove espaços extras entre letras da descrição
                            # Exemplo: "A T I V O" -> "ATIVO"
                            palavras = resto_linha.split()
                            
                            # Separa descrição de valores numéricos
                            descricao_parts = []
                            valores = []
                            
                            for palavra in palavras:
                                # Se contém números e formatação monetária
                                if re.search(r'[\d,\.]', palavra) and (palavra.count(',') > 0 or palavra.count('.') > 1):
                                    valores.append(palavra)
                                # Se é uma letra ou palavra da descrição
                                elif len(palavra) <= 3 and palavra.isalpha():
                                    descricao_parts.append(palavra)
                                # Se é palavra completa
                                elif palavra.isalpha() or palavra.isalnum():
                                    descricao_parts.append(palavra)
                                # Pode ser valor entre parênteses
                                elif '(' in palavra or ')' in palavra:
                                    valores.append(palavra)
                            
                            descricao = ' '.join(descricao_parts)
                            
                            # Organiza valores: saldo_anterior, debito, credito, saldo
                            saldo_anterior = valores[0] if len(valores) > 0 else ""
                            debito = valores[1] if len(valores) > 1 else ""
                            credito = valores[2] if len(valores) > 2 else ""
                            saldo = valores[3] if len(valores) > 3 else ""
                            
                            registro = {
                                "conta": conta,
                                "status": status,
                                "classificacao": classificacao,
                                "descricao": descricao,
                                "saldo_anterior": saldo_anterior,
                                "debito": debito,
                                "credito": credito,
                                "saldo": saldo,
                                "pagina": num_pagina
                            }
                            
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
            "descricao": "Balancete extraído do PDF"
        },
        "registros": registros
    }

def main():
    pdf_path = "balancete-f3.pdf"
    
    print(f"\n{'='*80}")
    print(f"EXTRAÇÃO DE DADOS DO BALANCETE")
    print(f"{'='*80}\n")
    print(f"Arquivo: {pdf_path}\n")
    
    resultado = extrair_dados_com_texto(pdf_path)
    
    if "erro" in resultado:
        print(f"\n❌ Erro: {resultado['erro']}")
        return
    
    # Salva em arquivo JSON
    output_file = "balancete-f3-final.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"RESULTADO DA EXTRAÇÃO")
    print(f"{'='*80}")
    print(f"✓ Total de registros extraídos: {resultado['metadata']['total_registros']}")
    print(f"✓ Arquivo salvo em: {output_file}")
    
    # Exibe preview
    print(f"\n{'='*80}")
    print(f"PREVIEW DOS PRIMEIROS 15 REGISTROS")
    print(f"{'='*80}\n")
    
    for i, reg in enumerate(resultado['registros'][:15]):
        print(f"[{i+1}] Conta: {reg['conta']} | Status: {reg['status']} | Pág: {reg['pagina']}")
        print(f"    Classificação: {reg['classificacao']}")
        print(f"    Descrição: {reg['descricao']}")
        print(f"    Saldo Anterior: {reg['saldo_anterior']}")
        print(f"    Débito: {reg['debito']}")
        print(f"    Crédito: {reg['credito']}")
        print(f"    Saldo: {reg['saldo']}")
        print()
    
    print(f"{'='*80}")
    print(f"✓ Extração concluída! Arquivo completo: {output_file}")
    print(f"{'='*80}\n")
    
    return resultado

if __name__ == "__main__":
    resultado = main()
