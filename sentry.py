def validar_requisicao(request):
    user_id_raw = request.form.get('user_id')
    file_id_raw = request.form.get('file_id')

    if user_id_raw is None or str(user_id_raw).strip() == "":
        raise ValueError("Campo 'user_id' é obrigatório e deve ser um inteiro.")

    if file_id_raw is None or str(file_id_raw).strip() == "":
        raise ValueError("Campo 'file_id' é obrigatório e deve ser um inteiro.")

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise ValueError("Campo 'user_id' deve ser um inteiro válido.")

    try:
        file_id = int(file_id_raw)
    except (TypeError, ValueError):
        raise ValueError("Campo 'file_id' deve ser um inteiro válido.")

    return (user_id, file_id)
