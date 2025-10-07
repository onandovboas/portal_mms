# cadastros/views.py
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Turma, Inscricao, RegistroAula, Professor, Presenca, Pagamento, Contrato, AcompanhamentoFalta, Aluno, Inscricao, RegistroAula, Presenca, Lead
from .forms import AlunoForm, PagamentoForm, AlunoExperimentalForm, ContratoForm, RegistroAulaForm, LeadForm
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import F, Sum, Count, Min, Q, Subquery, OuterRef, Max, DecimalField, Exists
from decimal import Decimal
from dateutil.relativedelta import relativedelta 
import calendar
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, render, redirect
import csv
from django.utils.encoding import smart_str
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.db.models.functions import ExtractWeek


# --- Views do Portal do Professor ---


@login_required
@login_required
def portal_professor(request):
    # 👇 A MUDANÇA ESTÁ NESTA LINHA 👇
    turmas_qs = Turma.objects.all().prefetch_related(
        'inscricao_set__aluno',  # Isso já existia
        'horarios'               # <-- Adicionamos isso para buscar os horários
    ).order_by('nome')
    
    turmas_info = []
    for turma in turmas_qs:
        turmas_info.append({
            'turma': turma,
            'matriculados_count': turma.inscricao_set.filter(status='matriculado').count(),
            'experimentais_count': turma.inscricao_set.filter(status='experimental').count(),
            'acompanhando_count': turma.inscricao_set.filter(status='acompanhando').count(),
            # O objeto 'turma' já vem com seus horários "anexados" graças ao prefetch_related
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
                return redirect('cadastros:portal_professor')

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

        return redirect('cadastros:detalhe_turma', pk=turma.pk)

    # --- LÓGICA GET ATUALIZADA ---
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    historico_aulas = RegistroAula.objects.filter(turma=turma, data_aula__year=ano_selecionado, data_aula__month=mes_selecionado).order_by('-data_aula')
    data_atual = date(ano_selecionado, mes_selecionado, 1)
    
    paginator = Paginator(historico_aulas, 5) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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
        'page_obj': page_obj,
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
    
    # --- LÓGICA DE FILTRO DE DATA ---
    ano_param = request.GET.get('ano') or hoje.year
    mes_param = request.GET.get('mes') or hoje.month
    ano_selecionado = int(ano_param)
    mes_selecionado = int(mes_param)
    data_selecionada = date(ano_selecionado, mes_selecionado, 1)

    # --- Lógica de Navegação ---
    mes_anterior = (data_selecionada.month - 2 + 12) % 12 + 1
    ano_anterior = data_selecionada.year if data_selecionada.month > 1 else data_selecionada.year - 1
    mes_seguinte = data_selecionada.month % 12 + 1
    ano_seguinte = data_selecionada.year if data_selecionada.month < 12 else data_selecionada.year + 1

    # --- Lógica para Capturar Filtros Adicionais ---
    turma_filtrada_id = request.GET.get('turma')
    tipo_filtrado = request.GET.get('tipo')

    # --- DEFINIR data_limite_renovacao ANTES de usar ---
    data_limite_renovacao = hoje + timedelta(days=30)

    # --- Consultas otimizadas ---
    pagamentos_pendentes = Pagamento.objects.filter(
        status__in=['pendente', 'parcial', 'atrasado'],
        mes_referencia__year=ano_selecionado,
        mes_referencia__month=mes_selecionado
    ).select_related('aluno', 'contrato')

    pagamentos_pagos = Pagamento.objects.filter(
        status='pago',
        mes_referencia__year=ano_selecionado,
        mes_referencia__month=mes_selecionado
    ).select_related('aluno', 'contrato')

    data_limite_renovacao = hoje + timedelta(days=30)
    contratos_a_vencer = Contrato.objects.filter(
        ativo=True, 
        data_fim__gte=hoje, 
        data_fim__lte=data_limite_renovacao
    ).select_related('aluno').order_by('data_fim')
    novos_contratos_subquery = Contrato.objects.filter(
        aluno=OuterRef('aluno'),      # Compara com o aluno do contrato externo
        data_inicio__gt=OuterRef('data_fim') # Verifica se o novo contrato começou DEPOIS do fim do antigo
    )

    # A query principal:
    # - Filtra contratos que já venceram (data_fim < hoje)
    # - Anota cada um com um booleano 'novo_contrato_existe'
    # - Filtra para manter apenas aqueles onde 'novo_contrato_existe' é False
    contratos_vencidos_sem_renovacao = Contrato.objects.filter(
        ativo=True,
        data_fim__lt=hoje
    ).annotate(
        novo_contrato_existe=Exists(novos_contratos_subquery)
    ).filter(
        novo_contrato_existe=False
    ).select_related('aluno').order_by('-data_fim')


    acompanhamentos_pendentes = AcompanhamentoFalta.objects.filter(
        status='pendente'
    ).select_related('aluno').order_by('criado_em')

    inscricoes_experimentais = Inscricao.objects.filter(
        status='experimental'
    ).select_related('aluno', 'turma')

    # Aplicar filtros adicionais se existirem
    if turma_filtrada_id:
        alunos_da_turma = Inscricao.objects.filter(turma__id=turma_filtrada_id).values_list('aluno__id', flat=True)
        pagamentos_pendentes = pagamentos_pendentes.filter(aluno__id__in=alunos_da_turma)
        pagamentos_pagos = pagamentos_pagos.filter(aluno__id__in=alunos_da_turma)

    if tipo_filtrado:
        pagamentos_pendentes = pagamentos_pendentes.filter(tipo=tipo_filtrado)
        pagamentos_pagos = pagamentos_pagos.filter(tipo=tipo_filtrado)

    pagamentos_pendentes = pagamentos_pendentes.order_by('aluno__nome_completo')
    pagamentos_pagos = pagamentos_pagos.order_by('-data_pagamento')

    # Preparar headers para as tabelas
    headers_renovacoes = ["Aluno", "Telefone", "Plano", "Fim do Contrato", "Status"]
    headers_experimentais = ["Aluno", "Telefone", "Turma", "Ações"]
    headers_pendentes = ["","Aluno", "Telefone", "Descrição", "Valor Restante", "Vencimento", "Status", "Ação Rápida"]
    headers_recebidos = ["Aluno", "Descrição", "Valor", "Data Pagamento", "Ações"]

    context = {
        'pagamentos_pendentes': pagamentos_pendentes,
        'pagamentos_pagos': pagamentos_pagos,
        'data_selecionada': data_selecionada,
        'contratos_a_vencer': contratos_a_vencer,
        'contratos_vencidos': contratos_vencidos_sem_renovacao,
        'acompanhamentos_pendentes': acompanhamentos_pendentes,
        'inscricoes_experimentais': inscricoes_experimentais,
        'nav': {
            'mes_anterior': mes_anterior, 
            'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 
            'ano_seguinte': ano_seguinte,
        },
        'todas_as_turmas': Turma.objects.all(),
        'tipos_de_pagamento': Pagamento.TIPO_CHOICES,
        'filtros_ativos': { 
            'turma': turma_filtrada_id, 
            'tipo': tipo_filtrado 
        },
        "headers_renovacoes": headers_renovacoes,
        "headers_experimentais": headers_experimentais,
        "headers_pendentes": headers_pendentes,
        "headers_recebidos": headers_recebidos,
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
        
    return redirect('cadastros:dashboard_admin')

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
        return redirect('cadastros:dashboard_admin')

    alunos = Aluno.objects.filter(status='ativo').order_by('nome_completo')
    return render(request, 'cadastros/lancamento_form.html', {'alunos': alunos})

@login_required
def relatorio_pagamento_professores(request):
    # --- Parte 1: Lógica de Filtro e Navegação (sem alterações) ---
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    data_selecionada = date(ano_selecionado, mes_selecionado, 1)

    mes_anterior = (data_selecionada.month - 2 + 12) % 12 + 1
    ano_anterior = data_selecionada.year if data_selecionada.month > 1 else data_selecionada.year - 1
    mes_seguinte = data_selecionada.month % 12 + 1
    ano_seguinte = data_selecionada.year if data_selecionada.month < 12 else data_selecionada.year + 1

    # --- Parte 2: Nova Consulta ao Banco de Dados ---
    # Agora, extraímos o número da semana e agrupamos por professor E por semana.
    relatorio_flat = RegistroAula.objects.filter(
        data_aula__year=ano_selecionado,
        data_aula__month=mes_selecionado
    ).annotate(
        semana=ExtractWeek('data_aula')  # Extrai o número da semana do ano
    ).values(
        'professor__nome_completo', 'semana'
    ).annotate(
        aulas_dadas=Count('id')
    ).order_by('professor__nome_completo', 'semana')

    # --- Parte 3: Processamento dos Dados em Python ---
    # Transformamos a lista "plana" em um dicionário aninhado para facilitar a renderização.
    relatorio_processado = {}
    for item in relatorio_flat:
        professor = item['professor__nome_completo']
        semana = item['semana']
        aulas = item['aulas_dadas']
        
        # Lógica para encontrar o início e fim da semana
        primeiro_dia_ano = date(ano_selecionado, 1, 1)
        # Ajuste para a semana começar na segunda-feira
        if primeiro_dia_ano.weekday() > 0:
            primeiro_dia_ano -= timedelta(days=primeiro_dia_ano.weekday())
        
        inicio_semana = primeiro_dia_ano + timedelta(weeks=semana - 1)
        fim_semana = inicio_semana + timedelta(days=6)

        if professor not in relatorio_processado:
            relatorio_processado[professor] = {
                'semanas': {},
                'total_mensal': 0
            }
        
        relatorio_processado[professor]['semanas'][semana] = {
            'aulas': aulas,
            'inicio': inicio_semana,
            'fim': fim_semana
        }
        relatorio_processado[professor]['total_mensal'] += aulas

    context = {
        'relatorio': relatorio_processado, # Enviamos o dicionário processado
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
        
        return redirect('cadastros:dashboard_admin')

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
    return redirect('cadastros:dashboard_admin')

@login_required
def quitar_pagamento_especifico(request, pk):
    # 1. Encontra o pagamento EXATO que foi clicado, usando o ID (pk).
    pagamento = get_object_or_404(Pagamento, pk=pk)

    # 2. Define a cobrança como totalmente paga, atualizando os campos necessários.
    pagamento.status = 'pago'
    pagamento.valor_pago = pagamento.valor
    pagamento.data_pagamento = timezone.now().date()
    pagamento.save()

    # 3. Redireciona o usuário de volta para o dashboard.
    return redirect('cadastros:dashboard_admin')

@login_required
def perfil_aluno(request, pk):
    # CONSULTA OTIMIZADA - Evita problemas N+1
    aluno = get_object_or_404(
        Aluno.objects.prefetch_related(
            'contratos',
            'pagamentos',
            'acompanhamentos',
            'presenca_set__registro_aula__turma',
            'inscricao_set__turma'
        ), 
        pk=pk
    )

    # Contrato ativo
    contrato_ativo = (Contrato.objects
                      .filter(aluno=aluno, ativo=True)
                      .filter(Q(data_fim__gte=timezone.now()) | Q(data_fim__isnull=True))
                      .order_by('-data_inicio')
                      .first())

    # HISTÓRICO DE TURMAS - Nova funcionalidade
    historico_turmas = (Inscricao.objects
                        .filter(aluno=aluno)
                        .select_related('turma')
                        .order_by('-id'))

    # ACOMPANHAMENTOS
    acompanhamentos = (AcompanhamentoFalta.objects
                       .filter(aluno=aluno)
                       .order_by('-criado_em'))

    # ESTATÍSTICAS DE FREQUÊNCIA
    presencas_stats = Presenca.objects.filter(aluno=aluno).aggregate(
        total_aulas=Count('id'),
        total_presencas=Count('id', filter=Q(presente=True)),
        total_faltas=Count('id', filter=Q(presente=False))
    )
    
    # Calcular percentual de frequência
    total_aulas = presencas_stats['total_aulas'] or 1  # Evita divisão por zero
    percentual_frequencia = (presencas_stats['total_presencas'] / total_aulas) * 100

    # Pagamentos
    pagamentos = (Pagamento.objects
                  .filter(aluno=aluno)
                  .order_by('-data_vencimento'))

    kpis = pagamentos.aggregate(
        pendentes=Count('id', filter=Q(status='pendente')),
        atrasados=Count('id', filter=Q(status='atrasado')),
    )

    # DADOS PARA GRÁFICO DE FREQUÊNCIA (ÚLTIMOS 6 MESES)
    meses_frequencia = []
    hoje = timezone.now().date()
    
    for i in range(5, -1, -1):  # Últimos 6 meses
        mes_data = hoje - relativedelta(months=i)
        mes_inicio = mes_data.replace(day=1)
        if i == 0:
            mes_fim = hoje
        else:
            mes_fim = mes_inicio + relativedelta(months=1) - timedelta(days=1)
        
        # Calcular frequência do mês
        presencas_mes = Presenca.objects.filter(
            aluno=aluno,
            registro_aula__data_aula__range=[mes_inicio, mes_fim]
        ).aggregate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True))
        )
        
        total_mes = presencas_mes['total'] or 0
        presentes_mes = presencas_mes['presentes'] or 0
        percentual_mes = (presentes_mes / total_mes * 100) if total_mes > 0 else 0
        
        meses_frequencia.append({
            'mes': mes_inicio.strftime('%b/%Y'),
            'percentual': round(percentual_mes, 1),
            'aulas': total_mes,
            'presencas': presentes_mes
        })

    context = {
        'meses_frequencia': meses_frequencia,
        'aluno': aluno,
        'contrato_ativo': contrato_ativo,
        'historico_turmas': historico_turmas,
        'acompanhamentos': acompanhamentos,
        'presencas_stats': presencas_stats,
        'percentual_frequencia': percentual_frequencia,
        'pagamentos': pagamentos,
        'kpis': kpis,
    }

    return render(request, 'cadastros/perfil_aluno.html', context)
@login_required
def exportar_pagamentos_aluno(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    qs = (Pagamento.objects
          .filter(aluno=aluno)
          .order_by('-data_vencimento'))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"pagamentos_{aluno.nome_completo.replace(' ', '_')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Aluno', 'Descrição', 'Tipo', 'Valor', 'Status',
        'Mês de Referência', 'Vencimento', 'Data Pagamento', 'Valor Pago', 'Contrato ID'
    ])
    for p in qs:
        writer.writerow([
            smart_str(aluno.nome_completo),
            smart_str(p.descricao),
            p.get_tipo_display(),
            f"{p.valor:.2f}",
            p.get_status_display(),
            p.mes_referencia.strftime("%Y-%m-%d") if p.mes_referencia else "",
            p.data_vencimento.strftime("%Y-%m-%d") if p.data_vencimento else "",
            p.data_pagamento.strftime("%Y-%m-%d") if p.data_pagamento else "",
            f"{p.valor_pago:.2f}",
            p.contrato_id or "",
        ])
    return response

@login_required
def novo_pagamento(request, pk):
    """
    Atalho: redireciona para o formulário de lançamento existente,
    pré-selecionando o aluno via querystring e definindo 'next' para voltar ao perfil.
    """
    # se você já tem a rota 'lancamento_recebimento' no urls do projeto, isso funciona:
    next_url = reverse('cadastros:perfil_aluno', args=[pk]) if request.resolver_match.namespace == 'cadastros' else reverse('perfil_aluno', args=[pk])
    lancamento_url = reverse('cadastros:lancamento_recebimento')  # essa rota está no urls do projeto raiz
    return HttpResponseRedirect(f"{lancamento_url}?aluno={pk}&next={next_url}")




def formulario_inscricao(request):
    # Por enquanto, esta view apenas exibe a página.
    # A lógica para salvar os dados virá depois.
    if request.method == 'POST':
        # Ação de salvar os dados virá aqui.
        pass

    return render(request, 'cadastros/inscricao_form.html')

@login_required
def editar_aluno(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)

    if request.method == "POST":
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do aluno atualizados com sucesso.")
            return redirect("cadastros:perfil_aluno", pk=aluno.pk) if request.resolver_match.namespace == "cadastros" else redirect("perfil_aluno", pk=aluno.pk)
        else:
            messages.error(request, "Corrija os campos destacados e tente novamente.")
    else:
        form = AlunoForm(instance=aluno)

    return render(request, "cadastros/editar_aluno.html", {
        "form": form,
        "aluno": aluno,
    })

@login_required
def relatorio_alunos_pendentes(request):
    # Esta consulta é o coração da funcionalidade.
    # 1. Filtramos apenas alunos que têm pagamentos com status de pendência.
    # 2. Usamos .annotate() para calcular novos campos para cada aluno:
    #    - total_devido: A soma do (valor total - valor já pago).
    #    - cobrancas_pendentes: A contagem de pagamentos em aberto.
    #    - vencimento_mais_antigo: A data de vencimento mais antiga entre as pendências.
    # 3. Filtramos novamente para garantir que só apareçam alunos com cobranças pendentes.
    # 4. Ordenamos para que os casos mais críticos (vencimento mais antigo) apareçam primeiro.
    
    alunos_com_pendencias = Aluno.objects.filter(
        pagamentos__status__in=['pendente', 'atrasado', 'parcial']
    ).annotate(
        total_devido=Sum(
            F('pagamentos__valor') - F('pagamentos__valor_pago'),
            filter=Q(pagamentos__status__in=['pendente', 'atrasado', 'parcial'])
        ),
        cobrancas_pendentes=Count(
            'pagamentos__id',
            filter=Q(pagamentos__status__in=['pendente', 'atrasado', 'parcial'])
        ),
        vencimento_mais_antigo=Min(
            'pagamentos__data_vencimento',
            filter=Q(pagamentos__status__in=['pendente', 'atrasado', 'parcial'])
        )
    ).filter(cobrancas_pendentes__gt=0).order_by('vencimento_mais_antigo')

    context = {
        'alunos': alunos_com_pendencias,
    }
    return render(request, 'cadastros/relatorio_alunos_pendentes.html', context)

@login_required
def lista_alunos(request):
    # Usamos Subquery para buscar informações de outros modelos de forma eficiente,
    # evitando o problema de N+1 queries.

    # Subquery para buscar o plano do contrato ativo mais recente.
    contrato_ativo_plano = Contrato.objects.filter(
        Q(aluno=OuterRef('pk')) & (Q(data_fim__gte=timezone.now()) | Q(data_fim__isnull=True)),
        ativo=True
    ).order_by('-data_inicio').values('plano')[:1]

    # Subquery para buscar o valor da mensalidade do mesmo contrato.
    contrato_ativo_valor = Contrato.objects.filter(
        Q(data_fim__gte=timezone.now()) | Q(data_fim__isnull=True),
        aluno=OuterRef('pk'), 
        ativo=True
    ).order_by('-data_inicio').values('valor_mensalidade')[:1]
    
    # Subquery para buscar a data do último pagamento efetuado.
    ultimo_pagamento = Pagamento.objects.filter(
        aluno=OuterRef('pk'),
        status='pago'
    ).order_by('-data_pagamento').values('data_pagamento')[:1]

    # A query principal anota (adiciona) as informações das subqueries a cada aluno.
    alunos = Aluno.objects.annotate(
        plano_contrato=Subquery(contrato_ativo_plano),
        valor_mensalidade_contrato=Subquery(contrato_ativo_valor),
        data_ultimo_pagamento=Subquery(ultimo_pagamento)
    ).order_by('nome_completo')

    context = {
        'alunos': alunos,
    }
    return render(request, 'cadastros/lista_alunos.html', context)

@login_required
def editar_pagamento(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    
    if request.method == 'POST':
        form = PagamentoForm(request.POST, instance=pagamento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pagamento atualizado com sucesso!')
            # Redireciona de volta para o dashboard, mantendo os filtros de mês/ano
            return redirect(request.GET.get('next', 'cadastros:dashboard_admin'))
    else:
        form = PagamentoForm(instance=pagamento)

    context = {
        'form': form,
        'pagamento': pagamento
    }
    return render(request, 'cadastros/editar_pagamento.html', context)

@login_required
def pagamentos_acoes_em_lote(request):
    if request.method == 'POST':
        pagamento_ids = request.POST.getlist('pagamento_ids')
        acao = request.POST.get('acao')

        if not pagamento_ids:
            messages.warning(request, 'Nenhum pagamento foi selecionado.')
            return redirect(request.META.get('HTTP_REFERER', 'cadastros:dashboard_admin'))

        queryset = Pagamento.objects.filter(pk__in=pagamento_ids)

        if acao == 'quitar':
            queryset.update(
                status='pago',
                valor_pago=F('valor'), # Define o valor pago igual ao valor total da cobrança
                data_pagamento=timezone.now().date()
            )
            messages.success(request, f'{len(pagamento_ids)} pagamento(s) foram quitados com sucesso.')
        
        # Aqui podemos adicionar outras ações no futuro (ex: elif acao == 'cancelar': ...)

    # Redireciona de volta para a página anterior (o dashboard)
    return redirect(request.META.get('HTTP_REFERER', 'cadastros:dashboard_admin'))

@require_POST # Garante que esta view só pode ser acessada via método POST, por segurança
@login_required
def quitar_dividas_aluno(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    
    # Encontra todos os pagamentos com status de pendência para este aluno
    pagamentos_pendentes = Pagamento.objects.filter(
        aluno=aluno,
        status__in=['pendente', 'parcial', 'atrasado']
    )
    
    # Usa o método .update() para atualizar todos de uma vez de forma eficiente
    pagamentos_pendentes.update(
        status='pago',
        valor_pago=F('valor'),
        data_pagamento=timezone.now().date()
    )
    
    messages.success(request, f'Todas as pendências de {aluno.nome_completo} foram quitadas.')
    
    # Redireciona de volta para a página de perfil do aluno
    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

@login_required
@login_required
def novo_aluno_experimental(request):
    lead_id = request.GET.get('lead_id') # Verifica se estamos vindo de uma conversão

    if request.method == 'POST':
        form = AlunoExperimentalForm(request.POST)
        if form.is_valid():
            aluno = form.save(commit=False)
            aluno.status = 'ativo'
            aluno.save()

            turma_selecionada = form.cleaned_data['turma_experimental']
            Inscricao.objects.create(
                aluno=aluno,
                turma=turma_selecionada,
                status='experimental'
            )
            
            # A MÁGICA FINAL: Se viemos de uma conversão, atualiza o status do Lead
            if lead_id:
                try:
                    lead = Lead.objects.get(pk=lead_id)
                    lead.status = 'convertido'
                    lead.save()
                    messages.success(request, f'Lead "{lead.nome_completo}" convertido com sucesso em aluno experimental!')
                except Lead.DoesNotExist:
                    pass # Se o lead não for encontrado, não faz nada
            else:
                messages.success(request, f'Aluno(a) {aluno.nome_completo} cadastrado(a) como experimental.')

            return redirect('cadastros:dashboard_admin')
    else:
        # Se recebermos dados via GET (do redirect), usamos para preencher o formulário
        initial_data = {
            'nome_completo': request.GET.get('nome_completo'),
            'email': request.GET.get('email'),
            'telefone': request.GET.get('telefone'),
        }
        form = AlunoExperimentalForm(initial=initial_data)

    context = {
        'form': form,
        'lead_id': lead_id, # Passa o ID do lead para o template
    }
    return render(request, 'cadastros/novo_aluno_experimental.html', context)

@login_required
def criar_contrato(request, aluno_pk):
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    if request.method == 'POST':
        form = ContratoForm(request.POST)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.aluno = aluno # Associa o contrato ao aluno correto
            contrato.save()

            # A MÁGICA DA AUTOMAÇÃO ACONTECE AQUI:
            # Busca a inscrição experimental do aluno e atualiza o status para 'matriculado'
            Inscricao.objects.filter(aluno=aluno, status='experimental').update(status='matriculado')

            messages.success(request, f'Contrato criado para {aluno.nome_completo}. Status atualizado para "Matriculado".')
            return redirect('cadastros:perfil_aluno', pk=aluno.pk) # Redireciona para o perfil do aluno
    else:
        form = ContratoForm()

    context = {
        'form': form,
        'aluno': aluno
    }
    return render(request, 'cadastros/criar_contrato.html', context)

@login_required
def editar_registro_aula(request, pk):
    registro_aula = get_object_or_404(RegistroAula, pk=pk)
    turma_pk = registro_aula.turma.pk # Guarda o ID da turma para o redirecionamento

    if request.method == 'POST':
        form = RegistroAulaForm(request.POST, instance=registro_aula)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registro de aula atualizado com sucesso!')
            # Redireciona de volta para a página de detalhes da turma
            return redirect('cadastros:detalhe_turma', pk=turma_pk)
    else:
        form = RegistroAulaForm(instance=registro_aula)

    context = {
        'form': form,
        'registro_aula': registro_aula
    }
    return render(request, 'cadastros/editar_registro_aula.html', context)

@login_required
def lista_leads(request):
    # Por padrão, vamos mostrar apenas os leads que precisam de atenção (não convertidos ou perdidos)
    leads_ativos = Lead.objects.exclude(status__in=['convertido', 'perdido'])
    
    context = {
        'leads': leads_ativos,
    }
    return render(request, 'cadastros/lista_leads.html', context)

@login_required
def adicionar_lead(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            messages.success(request, f'Lead "{lead.nome_completo}" adicionado com sucesso.')
            return redirect('cadastros:lista_leads')
    else:
        form = LeadForm()

    context = {
        'form': form
    }
    return render(request, 'cadastros/adicionar_lead.html', context)

@login_required
def editar_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lead "{lead.nome_completo}" atualizado com sucesso.')
            return redirect('cadastros:lista_leads')
    else:
        form = LeadForm(instance=lead)

    context = {
        'form': form,
        'lead': lead,
    }
    return render(request, 'cadastros/editar_lead.html', context)

@login_required
def converter_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    
    # Prepara os dados do lead para passar via URL
    # O redirect vai para o formulário de novo aluno experimental,
    # já com os campos preenchidos e com o ID do lead para referência.
    url_destino = reverse('cadastros:novo_aluno_experimental')
    parametros = f'?lead_id={lead.pk}&nome_completo={lead.nome_completo}&email={lead.email or ""}&telefone={lead.telefone or ""}'
    
    return redirect(url_destino + parametros)