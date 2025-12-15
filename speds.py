def processa_sped(sped_file):
    with open(sped_file, 'rb') as file:
        speds = file.readlines()

    for sped in speds:
        if b'|M210|' in sped:
            m210 = sped.decode('utf-8')
            if m210.startswith('|M210|'):
                m210_limpo = m210.strip()
                m210_campos = m210_limpo.split('|')
        
        if b'|M610|' in sped:
            m610 = sped.decode('utf-8')
            if m610.startswith('|M610|'):
                m610_limpo = m610.strip()
                m610_campos = m610_limpo.split('|')
        
        if b'|0000|' in sped:
            periodo = sped.decode('utf-8')
            if periodo.startswith('|0000|'):
                periodo_limpo = periodo.strip()
                periodo_campos = periodo_limpo.split('|')
                periodo_inicio = periodo_campos[6]
                periodo_fim = periodo_campos[7]
                periodo_inicio_formatado = f"{periodo_inicio[0:2]}/{periodo_inicio[2:4]}/{periodo_inicio[4:8]}"
                periodo_fim_formatado = f"{periodo_fim[0:2]}/{periodo_fim[2:4]}/{periodo_fim[4:8]}"
    
    return {
        'periodo': [periodo_inicio_formatado, periodo_fim_formatado],
        'm210': m210_campos[1:],
        'm610': m610_campos[1:]
    }
