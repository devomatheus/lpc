from db import test_connection, execute_query, execute_update, execute_many
from requests.exceptions import RequestException
from re import search as re_search
from dotenv import load_dotenv
from requests import delete
from copy import deepcopy
from os import getenv


load_dotenv()

API_URL = getenv("CURSOR_API_URL", None)
API_KEY = getenv("API_KEY_CURSOR", None)
CAMPOS_MONETARIOS = {'saldo_anterior', 'debito', 'credito', 'saldo_atual'}

headers = {
    "Content-Type": "application/json",
}

querys = {
    "verify_agents": "SELECT id_agente, status, branch, arquivo_id FROM agentes WHERE status IN ('CREATING', 'RUNNING', 'FINISHED')",
    "update_agent_status": "UPDATE agentes SET status = %s WHERE id_agente = %s",
    "update_conta_arquivo_status": "UPDATE conta_arquivos SET status_id = %s WHERE id = %s",
}


def fetch_analytical_accounts():
    query = (
        "SELECT conta_analiticas.*, classificacao_tributarias.tipo "
        "FROM conta_analiticas "
        "LEFT JOIN classificacao_tributarias "
        "ON conta_analiticas.classificacao_tributaria_id = classificacao_tributarias.id"
    )
    result = execute_query(query=query)
    return result


def converter_valores_para_centavos(data):
    """
    Função recursiva que converte valores monetários de reais para centavos.
    
    Percorre o JSON identificando campos monetários e convertendo valores float
    para inteiros (centavos), multiplicando por 100.
    
    Args:
        data: Dados JSON (dict, list ou valor primitivo)
    
    Returns:
        Dados JSON com valores monetários convertidos para centavos
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(key, str) and any(campo in key.lower() for campo in CAMPOS_MONETARIOS):
                if isinstance(value, (int, float)) and value is not None:
                    result[key] = int(round(value * 100))
                else:
                    result[key] = converter_valores_para_centavos(value)
            else:
                result[key] = converter_valores_para_centavos(value)
        return result
    elif isinstance(data, list):
        return [converter_valores_para_centavos(item) for item in data]
    else:
        return data


def closed_agent(agentes):
    print(f"Enviando requisição para API do Cursor...")
    endpoint = f"{API_URL}/{agentes.get('id_agente', None)}"
    headers['Authorization'] = f"Bearer {API_KEY}"

    try:
        response = delete(endpoint, headers=headers, timeout=300)
        response.raise_for_status()
        print(f"Agente {agentes.get('id_agente', None)} fechado com sucesso")
        
    except RequestException as e:
        print(f"Erro na requisição: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Resposta: {e.response.text}")
        raise

    except Exception as e:
        print(f"Erro ao processar: {e}")
        raise


def update_agent_status(agentes, status):
    execute_update(
        query=querys.get("update_agent_status", None), 
        params=(status, agentes['id_agente'])
    )


def update_conta_arquivo_status(arquivo_id, status_id=3):
    """
    Atualiza o campo status_id na tabela conta_arquivo.
    Usa o arquivo_id do dicionário agentes para identificar o registro.
    
    Args:
        agentes: Dicionário com informações do agente, incluindo arquivo_id
        status_id: Valor do status_id a ser atualizado (padrão: 3)
    """
    if not arquivo_id:
        print("Erro: arquivo_id não encontrado no dicionário agentes")
        return None
    
    linhas_afetadas = execute_update(
        query=querys.get("update_conta_arquivo_status", None),
        params=(status_id, arquivo_id)
    )
    # print(f"Status do conta_arquivo (id={arquivo_id}) atualizado para {status_id}. Linhas afetadas: {linhas_afetadas}")
    return linhas_afetadas


def get_data_complements(contas_analiticas, accounts_approved, accounts_rejected):
    descricao_to_conta = {
        conta.get('descricao'): conta
        for conta in (contas_analiticas or [])
        if conta.get('descricao')
    }

    enriched_approved = []
    for account in accounts_approved:
        descricao = account.get('account')
        enriched_account = deepcopy(account)

        conta_correspondente = descricao_to_conta.get(descricao)
        if conta_correspondente:
            enriched_account['aliquota_cbs'] = conta_correspondente.get('aliquota_cbs')
            enriched_account['aliquota_ibs'] = conta_correspondente.get('aliquota_ibs')
            enriched_account['classificacao_tributaria_id'] = conta_correspondente.get('classificacao_tributaria_id')
            enriched_account['id_conta_cenario_base_rumo'] = conta_correspondente.get('id')
        else:
            enriched_account['aliquota_cbs'] = None
            enriched_account['aliquota_ibs'] = None
            enriched_account['classificacao_tributaria_id'] = None
            enriched_account['id_conta_cenario_base_rumo'] = None

        enriched_account['tipo'] = True
        enriched_approved.append(enriched_account)

    enriched_rejected = []
    for account in accounts_rejected:
        enriched_account = deepcopy(account)
        enriched_account['aliquota_cbs'] = None
        enriched_account['aliquota_ibs'] = None
        enriched_account['classificacao_tributaria_id'] = None
        enriched_account['id_conta_cenario_base_rumo'] = None
        enriched_account['tipo'] = False
        enriched_rejected.append(enriched_account)

    return {
        'accounts_approved': enriched_approved,
        'accounts_rejected': enriched_rejected,
    }


def converter_data_para_iso(data_str):
    """
    Converte data do formato DD/MM/YYYY para YYYY-MM-DD (formato ISO para PostgreSQL).
    
    Args:
        data_str: Data no formato DD/MM/YYYY
    
    Returns:
        Data no formato YYYY-MM-DD ou None se inválida
    """
    if not data_str:
        return None
    
    try:
        partes = data_str.split('/')
        if len(partes) == 3:
            dia, mes, ano = partes
            return f"{ano}-{mes}-{dia}"
    except Exception:
        pass
    
    return None


def extrair_datas_periodo(period_str):
    """
    Extrai data_inicial, data_final e ano_base do campo period do header.
    Exemplo: "01/01/2025 - 30/06/2025" -> data_inicial="2025-01-01", data_final="2025-06-30", ano_base=2025
    Retorna as datas no formato ISO (YYYY-MM-DD) para PostgreSQL.
    """
    if not period_str:
        return None, None, None
    
    regex_data = r'\b\d{2}/\d{2}/\d{4}\b'
    pattern = rf'({regex_data})\s*-\s*({regex_data})'
    match = re_search(pattern, period_str)
    
    if match:
        data_inicial_br = match.group(1)
        data_final_br = match.group(2)

        data_inicial = converter_data_para_iso(data_inicial_br)
        data_final = converter_data_para_iso(data_final_br)

        ano_base = int(data_inicial_br.split('/')[2])
        return data_inicial, data_final, ano_base
    

    match_unica = re_search(regex_data, period_str)
    if match_unica:
        data_br = match_unica.group(0)
        data_iso = converter_data_para_iso(data_br)
        ano_base = int(data_br.split('/')[2])
        return data_iso, data_iso, ano_base
    
    return None, None, None


def converter_valor_para_centavos(valor_str):
    """
    Converte valor monetário do formato brasileiro para centavos (inteiro).
    
    Exemplos:
        "0,00" -> 0
        "1.234,56" -> 123456
        "889,70" -> 88970
        "21.209.514,46" -> 2120951446
    
    Args:
        valor_str: Valor no formato brasileiro (ex: "1.234,56")
    
    Returns:
        Valor em centavos (inteiro)
    """
    if not valor_str:
        return 0
    
    try:
        valor_limpo = valor_str.replace('.', '').replace(',', '.')
        valor_float = float(valor_limpo)
        return int(round(valor_float * 100))
    except (ValueError, AttributeError):
        return 0


def converter_classification_para_tupla(classification):
    """
    Converte uma classification em uma tupla de números para ordenação hierárquica.
    
    Exemplos:
        "1" -> (1,)
        "1.1" -> (1, 1)
        "3.1.01" -> (3, 1, 1)
        "3.1.01.01" -> (3, 1, 1, 1)
        "1.1.01.010.002" -> (1, 1, 1, 10, 2)
    
    Args:
        classification: String com a classification (ex: "3.1.01.01")
    
    Returns:
        Tupla de inteiros para ordenação
    """
    if not classification:
        return (0,)
    
    try:
        partes = classification.split('.')
        return tuple(int(parte) for parte in partes)
    except (ValueError, AttributeError):
        return (0,)


def ordenar_contas_por_classification(contas):
    """
    Ordena as contas pelo campo classification (grau_detalhamento) de forma hierárquica.
    
    Args:
        contas: Lista de dicionários com contas
    
    Returns:
        Lista de contas ordenadas
    """
    def chave_ordenacao(conta):
        classification = conta.get('classification', '')
        return converter_classification_para_tupla(classification)
    
    return sorted(contas, key=chave_ordenacao)


def preparar_dados_para_insert(todas_contas, arquivo_id, data_inicial, data_final, ano_base):
    """
    Prepara os dados para inserção na tabela conta_clientes.
    
    Args:
        todas_contas: Lista com todas as contas (approved + rejected)
        arquivo_id: ID do arquivo
        data_inicial: Data inicial do período
        data_final: Data final do período
        ano_base: Ano base do período
    
    Returns:
        Lista de tuplas com os dados para insert
    """
    dados_insert = []
    
    for ordem, conta in enumerate(todas_contas, start=1):
        grau_detalhamento = conta.get('classification')
        descricao = conta.get('account')
        
        saldo_anterior = converter_valor_para_centavos(conta.get('previous_balance', '0,00'))
        total_debito = converter_valor_para_centavos(conta.get('debit', '0,00'))
        total_credito = converter_valor_para_centavos(conta.get('credit', '0,00'))
        saldo_atual = converter_valor_para_centavos(conta.get('current_balance', '0,00'))
        
        id_conta_cenario_base_rumo = conta.get('id_conta_cenario_base_rumo')
        tipo = conta.get('tipo')
        
        natureza_conta = None
        receita_despesa = None
        
        dados_insert.append((
            ordem,
            grau_detalhamento,
            descricao,
            natureza_conta,
            receita_despesa,
            data_inicial,
            data_final,
            saldo_anterior,
            total_debito,
            total_credito,
            saldo_atual,
            ano_base,
            id_conta_cenario_base_rumo,
            arquivo_id,
            tipo
        ))
    
    return dados_insert


def inserir_contas_arquivo(dados_insert):
    """
    Insere as contas na tabela conta_clientes em lote.
    
    Args:
        dados_insert: Lista de tuplas com os dados para insert
    """
    if not dados_insert:
        print("Nenhum dado para inserir")
        return
    
    query = """
        INSERT INTO conta_clientes (
            ordem,
            grau_detalhamento,
            descricao,
            natureza_conta,
            receita_despesa,
            data_inicial,
            data_final,
            saldo_anterior,
            total_debito,
            total_credito,
            saldo_atual,
            ano_base,
            id_conta_cenario_base_rumo,
            arquivo_id,
            tipo
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        execute_many(query, dados_insert)
        # print(f"Inseridas {linhas_afetadas} contas na tabela conta_clientes")
    except Exception as e:
        print(f"Erro ao inserir contas na tabela conta_clientes: {e}")
        raise


def cross_references(analytical_accounts_parsed, arquivo_id=None):

    contas_analiticas = fetch_analytical_accounts()

    # print('iniciando cross references')
    accounts_approved = []
    accounts_rejected = []
    approved_seen = set()
    rejected_seen = set()

    # with open("temp/balancete.json", "r", encoding='utf-8') as f:
    #     analytical_accounts_parsed = load(f)

    header = analytical_accounts_parsed.get('header', {})
    period_str = header.get('period', '')
    data_inicial, data_final, ano_base = extrair_datas_periodo(period_str)
    
    # print(f"Período extraído: {data_inicial} - {data_final}, Ano base: {ano_base}")

    accounts = analytical_accounts_parsed.get('data', [])

    accounts_to_reference = []
    for account in accounts:
        classification = account.get('classification')
        if not classification:
            continue

        if isinstance(classification, str):
            first_char = classification[0]
        elif isinstance(classification, (list, tuple)):
            first_item = classification[0] if classification else ""
            first_char = first_item[0] if isinstance(first_item, str) and first_item else ""
        else:
            first_char = ""

        if first_char in {"3", "4"}:
            accounts_to_reference.append(account)

    descricoes_banco = {
        conta.get('descricao')
        for conta in (contas_analiticas or [])
        if conta.get('descricao')
    }

    for account in accounts_to_reference:
        descricao = account.get('account')

        if not descricao:
            continue

        if descricao in descricoes_banco:
            if descricao not in approved_seen:
                accounts_approved.append(deepcopy(account))
                approved_seen.add(descricao)
        else:
            if descricao not in rejected_seen:
                accounts_rejected.append(deepcopy(account))
                rejected_seen.add(descricao)

    data_complements = get_data_complements(
        contas_analiticas, 
        accounts_approved, 
        accounts_rejected
    )

    todas_contas = data_complements['accounts_approved'] + data_complements['accounts_rejected']
    
    todas_contas = ordenar_contas_por_classification(todas_contas)
    
    for conta in todas_contas:
        conta['ordem'] = None
        conta['data_inicial'] = data_inicial
        conta['data_final'] = data_final
        conta['ano_base'] = ano_base
        conta['arquivo_id'] = arquivo_id
    
    if arquivo_id:
        dados_insert = preparar_dados_para_insert(
            todas_contas, arquivo_id, data_inicial, 
            data_final, ano_base
        )
        inserir_contas_arquivo(dados_insert)
    
    for ordem, conta in enumerate(todas_contas, start=1):
        conta['ordem'] = ordem

    return data_complements


# def parse_agent_result(agentes, response):
#     branch = agentes.get('branch', 'main')
#     arquivo_id = agentes.get('arquivo_id')
#     download_parser_pdf = dpp(branch)
#     if download_parser_pdf:
#         print("Parser PDF baixado com sucesso")
#         closed_agent(agentes)

#         print("Agente fechado com sucesso")
#         update_conta_arquivo_status(agentes)
        
#         print("Status do conta_arquivo atualizado com sucesso")
#         update_agent_status(agentes, "FINISHED")

#         print("Status do agente atualizado para FINISHED")
#         response = fetch_analytical_accounts(arquivo_id)

#         print("Contas analíticas buscadas com sucesso")
#         return response
#     else:
#         print("Erro ao baixar parser PDF")
#         return None


# def verify_agent_status(agentes, response):
#     # status_atual_banco = agentes.get("status", None)
#     status_api = response.get("status", None)

#     if status_api is None:
#         print("Resposta do agente não contém status. Nenhuma ação executada.")
#         return None
    
#     # if status_atual_banco == status_api:
#     #         print("Status do agente atual é igual ao status da API. Nenhuma ação executada.")
#     #         return None

#     if status_api == "RUNNING":
#         update_agent_status(agentes, status_api)

#     if status_api == "FINISHED":
#         print("Status do agente atual é igual a FINISHED. Iniciando processo de parse...")
#         response = parse_agent_result(agentes, response)
#         return response


# def verify_agents_current(agentes):
#     """"""
#     endpoint = f"{API_URL}/{agentes.get('id_agente', None)}"
#     headers['Authorization'] = f"Bearer {API_KEY}"
#     try:
#         response = get(endpoint, headers=headers, timeout=300)
#         response.raise_for_status()
#         response = verify_agent_status(agentes, response.json())
#         return response
        
#     except RequestException as e:
#         print(f"Erro na requisição: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Status code: {e.response.status_code}")
#             print(f"Resposta: {e.response.text}")
#         raise

#     except Exception as e:
#         print(f"Erro ao processar: {e}")
#         raise


# def verify_agents():
#     """"""
#     if test_connection():
#         results = execute_query(
#             query=querys.get("verify_agents", None), 
#             fetch=True
#         )
#         if results:
#             for result in results:
#                 response = verify_agents_current(result)
#                 return response
#         else:
#             print("Nenhum agente encontrado")
#             return None
#     else:
#         print("Erro ao conectar ao banco de dados")
#         return None
