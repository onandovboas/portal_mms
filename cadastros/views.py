# cadastros/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Turma, Inscricao, RegistroAula, Professor, Presenca, Pagamento, Contrato, AcompanhamentoFalta, Aluno
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Count
from decimal import Decimal
from dateutil.relativedelta import relativedelta 
import calendar
from django.db.models import Sum, F, DecimalField
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST




# --- Views do Portal do Professor ---

@login_required
@login_required
def portal_professor(request):
    turmas_qs = Turma.objects.all().order_by('nome')
    
    turmas_info = []
    for turma in turmas_qs:
        # Agora contamos os 3 status
        turmas_info.append({
            'turma': turma,
            'matriculados_count': turma.inscricao_set.filter(status='matriculado').count(),
            'experimentais_count': turma.inscricao_set.filter(status='experimental').count(),
            'acompanhando_count': turma.inscricao_set.filter(status='acompanhando').count(),
        })

    context = {
        'turmas_info': turmas_info,
    }
    return render(request, 'cadastros/portal.html', context)


@login_required
def detalhe_turma(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    
    if request.method == 'POST':
        # ... (A lógica do POST para salvar anotações e aulas continua a mesma) ...
        if 'salvar_aula' in request.POST:
            try:
                professor = Professor.objects.get(usuario=request.user)
            except Professor.DoesNotExist:
                return redirect('portal_professor')

            novo_registro = RegistroAula.objects.create(
                turma=turma, professor=professor, data_aula=date.today(),
                last_word=request.POST.get('last_word'),
                last_parag=request.POST.get('last_parag') or None,
                new_dictation=request.POST.get('new_dictation') or None,
                old_dictation=request.POST.get('old_dictation') or None,
                new_reading=request.POST.get('new_reading') or None,
                old_reading=request.POST.get('old_reading') or None,
                lesson_check=request.POST.get('lesson_check'),
            )
            
            alunos_presentes_ids = request.POST.getlist('presenca')
            # Usamos a união das listas de alunos para registrar a presença
            todos_os_inscritos = list(turma.inscricao_set.filter(status__in=['matriculado', 'experimental', 'acompanhando']))
            for inscricao in todos_os_inscritos:
                Presenca.objects.create(
                    registro_aula=novo_registro, aluno=inscricao.aluno,
                    presente=(str(inscricao.aluno.pk) in alunos_presentes_ids)
                )

        elif 'salvar_anotacoes' in request.POST:
            novas_anotacoes = request.POST.get('anotacoes_gerais')
            turma.anotacoes_gerais = novas_anotacoes
            turma.save()

        elif 'salvar_detalhes_turma' in request.POST:
            novo_nome = request.POST.get('nome_turma')
            novo_stage = request.POST.get('stage_turma')
            if novo_nome:
                turma.nome = novo_nome
            if novo_stage:
                turma.stage = novo_stage
            turma.save()

        return redirect('detalhe_turma', pk=turma.pk)

    # --- LÓGICA GET ATUALIZADA ---
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    historico_aulas = RegistroAula.objects.filter(turma=turma, data_aula__year=ano_selecionado, data_aula__month=mes_selecionado).order_by('-data_aula')
    data_atual = date(ano_selecionado, mes_selecionado, 1)
    
    # ... (lógica de navegação de meses continua a mesma) ...
    mes_anterior = (data_atual.month - 2 + 12) % 12 + 1
    ano_anterior = data_atual.year if data_atual.month > 1 else data_atual.year - 1
    mes_seguinte = data_atual.month % 12 + 1
    ano_seguinte = data_atual.year if data_atual.month < 12 else data_atual.year + 1
    
    # 👇 A GRANDE MUDANÇA ESTÁ AQUI 👇
    # Em vez de uma lista, agora temos listas separadas por status.
    inscritos_matriculados = Inscricao.objects.filter(turma=turma, status='matriculado')
    inscritos_experimentais = Inscricao.objects.filter(turma=turma, status='experimental')
    inscritos_acompanhando = Inscricao.objects.filter(turma=turma, status='acompanhando')
    inscritos_trancados = Inscricao.objects.filter(turma=turma, status='trancado')
    
    context = {
        'turma': turma,
        # 👇 Enviamos as listas separadas para o template 👇
        'matriculados': inscritos_matriculados,
        'experimentais': inscritos_experimentais,
        'acompanhando': inscritos_acompanhando,
        'trancados': inscritos_trancados,
        
        'historico_aulas': historico_aulas,
        'data_selecionada': data_atual,
        'nav': {
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        }
    }
    return render(request, 'cadastros/detalhe_turma.html', context)


# --- Views do Dashboard do Administrador ---


@login_required
def dashboard_admin(request):
    hoje = timezone.now().date()
    
    # --- LÓGICA DE FILTRO DE DATA (sem alterações) ---
    ano_param = request.GET.get('ano') or hoje.year
    mes_param = request.GET.get('mes') or hoje.month
    ano_selecionado = int(ano_param)
    mes_selecionado = int(mes_param)
    data_selecionada = date(ano_selecionado, mes_selecionado, 1)

    # --- Lógica de Navegação (sem alterações) ---
    mes_anterior = (data_selecionada.month - 2 + 12) % 12 + 1
    ano_anterior = data_selecionada.year if data_selecionada.month > 1 else data_selecionada.year - 1
    mes_seguinte = data_selecionada.month % 12 + 1
    ano_seguinte = data_selecionada.year if data_selecionada.month < 12 else data_selecionada.year + 1

    # --- Lógica para Capturar Filtros Adicionais (sem alterações) ---
    turma_filtrada_id = request.GET.get('turma')
    tipo_filtrado = request.GET.get('tipo')

    # --- Lógica de Busca de Dados (sem alterações) ---
    pagamentos_pendentes = Pagamento.objects.filter(
        status__in=['pendente', 'parcial', 'atrasado'],
        mes_referencia__year=ano_selecionado,
        mes_referencia__month=mes_selecionado
    )
    pagamentos_pagos = Pagamento.objects.filter(
        status='pago',
        mes_referencia__year=ano_selecionado,
        mes_referencia__month=mes_selecionado
    )

    if turma_filtrada_id:
        alunos_da_turma = Inscricao.objects.filter(turma__id=turma_filtrada_id).values_list('aluno__id', flat=True)
        pagamentos_pendentes = pagamentos_pendentes.filter(aluno__id__in=alunos_da_turma)
        pagamentos_pagos = pagamentos_pagos.filter(aluno__id__in=alunos_da_turma)

    if tipo_filtrado:
        pagamentos_pendentes = pagamentos_pendentes.filter(tipo=tipo_filtrado)
        pagamentos_pagos = pagamentos_pagos.filter(tipo=tipo_filtrado)

    pagamentos_pendentes = pagamentos_pendentes.order_by('aluno__nome_completo')
    pagamentos_pagos = pagamentos_pagos.order_by('-data_pagamento')

    data_limite_renovacao = hoje + timedelta(days=30)
    contratos_a_vencer = Contrato.objects.filter(ativo=True, data_fim__gte=hoje, data_fim__lte=data_limite_renovacao).order_by('data_fim')
    acompanhamentos_pendentes = AcompanhamentoFalta.objects.filter(status='pendente').order_by('criado_em')
    inscricoes_experimentais = Inscricao.objects.filter(status='experimental')
    
    # O CONTEXTO FOI SIMPLIFICADO - REMOVEMOS AS BUSCAS POR SALDO DE CRÉDITO/DÉBITO
    context = {
        'pagamentos_pendentes': pagamentos_pendentes,
        'pagamentos_pagos': pagamentos_pagos,
        'data_selecionada': data_selecionada,
        'contratos_a_vencer': contratos_a_vencer,
        'acompanhamentos_pendentes': acompanhamentos_pendentes,
        'inscricoes_experimentais': inscricoes_experimentais,
        'nav': {
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        },
        'todas_as_turmas': Turma.objects.all(),
        'tipos_de_pagamento': Pagamento.TIPO_CHOICES,
        'filtros_ativos': { 'turma': turma_filtrada_id, 'tipo': tipo_filtrado }
    }
    return render(request, 'cadastros/dashboard.html', context)



@login_required
def resolver_acompanhamento(request, pk):
    if request.method == 'POST':
        acompanhamento = get_object_or_404(AcompanhamentoFalta, pk=pk)
        motivo = request.POST.get('motivo')
        
        acompanhamento.status = 'resolvido'
        acompanhamento.motivo = motivo
        acompanhamento.data_resolucao = timezone.now()
        acompanhamento.save()
        
    return redirect('dashboard_admin')

@login_required
def lancamento_recebimento(request):
    if request.method == 'POST':
        aluno_id = request.POST.get('aluno')
        valor_recebido = Decimal(request.POST.get('valor'))

        aluno = get_object_or_404(Aluno, pk=aluno_id)

        cobranca_aberta = Pagamento.objects.filter(
            aluno=aluno,
            status__in=['pendente', 'parcial', 'atrasado']
        ).order_by('data_vencimento').first()

        if cobranca_aberta:
            cobranca_aberta.valor_pago += valor_recebido
            if cobranca_aberta.valor_pago >= cobranca_aberta.valor:
                cobranca_aberta.status = 'pago'
                cobranca_aberta.data_pagamento = timezone.now().date()
            else:
                cobranca_aberta.status = 'parcial'
            cobranca_aberta.save()

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('dashboard_admin')

    alunos = Aluno.objects.filter(status='ativo').order_by('nome_completo')
    return render(request, 'cadastros/lancamento_form.html', {'alunos': alunos})

@login_required
def relatorio_pagamento_professores(request):
    # Lógica de Filtro de Data (igual ao dashboard)
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    data_selecionada = date(ano_selecionado, mes_selecionado, 1)

    # Lógica de Navegação de Meses
    mes_anterior = (data_selecionada.month - 2 + 12) % 12 + 1
    ano_anterior = data_selecionada.year if data_selecionada.month > 1 else data_selecionada.year - 1
    mes_seguinte = data_selecionada.month % 12 + 1
    ano_seguinte = data_selecionada.year if data_selecionada.month < 12 else data_selecionada.year + 1

    # A MÁGICA DA CONTAGEM ACONTECE AQUI
    # Filtra os registros de aula pelo mês/ano, agrupa por professor e conta quantos registros cada um tem.
    relatorio = RegistroAula.objects.filter(
        data_aula__year=ano_selecionado,
        data_aula__month=mes_selecionado
    ).values(
        'professor__nome_completo' # Agrupa pelo nome do professor
    ).annotate(
        aulas_dadas=Count('id') # Conta a quantidade de aulas (id) para cada grupo
    ).order_by('-aulas_dadas') # Ordena do que deu mais aulas para o que deu menos

    context = {
        'relatorio': relatorio,
        'data_selecionada': data_selecionada,
        'nav': {
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        }
    }
    return render(request, 'cadastros/relatorio_professores.html', context)

@login_required
def venda_livro(request):
    if request.method == 'POST':
        aluno_id = request.POST.get('aluno')
        descricao = request.POST.get('descricao')
        valor_total = Decimal(request.POST.get('valor'))
        numero_parcelas = int(request.POST.get('parcelas'))
        
        aluno = get_object_or_404(Aluno, pk=aluno_id)
        valor_parcela = round(valor_total / numero_parcelas, 2)
        hoje = timezone.now().date()

        # Loop para criar uma cobrança para cada parcela nos meses seguintes
        for i in range(numero_parcelas):
            # Calcula o mês de referência e vencimento para cada parcela
            mes_futuro = hoje + relativedelta(months=i)
            ultimo_dia_futuro = calendar.monthrange(mes_futuro.year, mes_futuro.month)[1]
            data_vencimento_parcela = mes_futuro.replace(day=ultimo_dia_futuro)

            Pagamento.objects.create(
                aluno=aluno,
                tipo='material',
                descricao=f"{descricao} (Parcela {i + 1}/{numero_parcelas})",
                valor=valor_parcela,
                mes_referencia=mes_futuro,
                data_vencimento=data_vencimento_parcela,
                status='pendente'
            )
        
        return redirect('dashboard_admin')

    # Lógica GET: Apenas exibe o formulário
    alunos = Aluno.objects.filter(status='ativo').order_by('nome_completo')
    context = {
        'alunos': alunos,
    }
    return render(request, 'cadastros/venda_livro_form.html', context)

@login_required
@require_POST
def pagamentos_bulk(request):
    ids = request.POST.getlist('ids')  # lista de pagamentos selecionados
    action = request.POST.get('action', 'quitar')
    next_url = request.POST.get('next') or request.GET.get('next')

    if action == 'quitar' and ids:
        # apenas registros ainda não pagos
        qs = Pagamento.objects.filter(id__in=ids).exclude(status='pago')
        hoje = timezone.now().date()
        for p in qs:
            # marca como quitado
            p.valor_pago = p.valor
            p.status = 'pago'
            if not p.data_pagamento:
                p.data_pagamento = hoje
            p.save(update_fields=['valor_pago', 'status', 'data_pagamento'])

    # Redireciona de volta para o mês/filtros atuais se for seguro
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('dashboard_admin')