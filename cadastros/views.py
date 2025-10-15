# cadastros/views.py
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Turma, Inscricao, RegistroAula, Professor, Presenca, Pagamento, Contrato, AcompanhamentoFalta, Aluno, Inscricao, RegistroAula, Presenca, Lead, TokenAtualizacaoAluno, AcompanhamentoPedagogico, AlunoProva, Questao, ProvaTemplate, RespostaAluno
from .forms import AlunoForm, PagamentoForm, AlunoExperimentalForm, ContratoForm, RegistroAulaForm, LeadForm, AcompanhamentoPedagogicoForm, LiberarProvaForm
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
from django.contrib.auth.models import User # <-- Adicione este import
import re
from django.utils.crypto import get_random_string
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django import forms
from django.db import transaction
from django.utils.html import format_html



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

    alunos_da_turma_ids = Inscricao.objects.filter(turma=turma).values_list('aluno_id', flat=True)
    provas_da_turma = AlunoProva.objects.filter(
        aluno_id__in=alunos_da_turma_ids
    ).select_related('aluno', 'prova_template').order_by('-data_realizacao')

    # --- LÓGICA GET ATUALIZADA ---
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    data_atual = date(ano_selecionado, mes_selecionado, 1)
    # ✅ MUDANÇA 1: Query otimizada com prefetch_related
    # Buscamos as aulas e, de forma eficiente, já "anexamos" a elas
    # todos os registros de presença e os alunos correspondentes.
    historico_aulas = RegistroAula.objects.filter(
    turma=turma, 
    data_aula__year=ano_selecionado, 
    data_aula__month=mes_selecionado
    ).select_related('professor').prefetch_related('presenca_set__aluno').order_by('-data_aula')
    

    alunos_ativos_na_turma = Aluno.objects.filter(
        inscricao__turma=turma, 
        inscricao__status__in=['matriculado', 'experimental', 'acompanhando']
    ).distinct()
    
    mapa_alunos_ativos = {aluno.pk: aluno for aluno in alunos_ativos_na_turma}
    set_ids_alunos_ativos = set(mapa_alunos_ativos.keys())

    for aula in historico_aulas:
        aula.alunos_ausentes = [
            p.aluno.nome_completo.split(' ')[0]  # <-- MUDANÇA AQUI
            for p in aula.presenca_set.all() 
            if not p.presente
        ]

    faltas_do_mes = Presenca.objects.filter(
        registro_aula__turma=turma,
        registro_aula__data_aula__year=ano_selecionado,
        registro_aula__data_aula__month=mes_selecionado,
        presente=False
    ).values(
        'aluno__nome_completo'  # Agrupa por este campo
    ).annotate(
        total_faltas=Count('id')  # Conta as ocorrências em cada grupo
    ).order_by('-total_faltas') # Ordena para mostrar quem mais faltou primeiro

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
        'aulas_do_mes': historico_aulas,
        'experimentais': inscritos_experimentais,
        'acompanhando': inscritos_acompanhando,
        'trancados': inscritos_trancados,
        'faltas_do_mes': faltas_do_mes,
        'historico_aulas': historico_aulas,
        'data_selecionada': data_atual,
        'provas_da_turma': provas_da_turma,
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
    # A ordem das colunas no Kanban será definida por esta lista
    ordem_status = ['novo', 'contatado', 'agendado', 'convertido', 'perdido']
    
    # Busca todos os leads e transforma-os num dicionário agrupado por status
    leads_todos = Lead.objects.all().order_by('-data_criacao')
    leads_por_status = {status: [] for status, _ in Lead.STATUS_CHOICES}
    for lead in leads_todos:
        leads_por_status[lead.status].append(lead)
    
    # Monta a estrutura de dados para o template, respeitando a ordem definida
    colunas_kanban = []
    for status_key in ordem_status:
        # Encontra o nome legível do status (ex: 'Novo Contato')
        status_display = dict(Lead.STATUS_CHOICES).get(status_key)
        colunas_kanban.append({
            'id': status_key,
            'titulo': status_display,
            'leads': leads_por_status.get(status_key, [])
        })

    context = {
        'colunas': colunas_kanban,
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

@login_required
def gerar_link_atualizacao(request, aluno_pk):
    """
    View para o administrador gerar um link de atualização para um aluno.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    
    # Cria um novo token no banco de dados associado ao aluno
    token_obj = TokenAtualizacaoAluno.objects.create(aluno=aluno)
    
    # Constrói a URL completa que será enviada ao aluno
    link_atualizacao = request.build_absolute_uri(
        reverse('cadastros:atualizar_dados_aluno', args=[token_obj.token])
    )
    
    # Adiciona uma mensagem de sucesso com o link para o admin copiar
    messages.success(
        request, 
        f"Link de atualização gerado para {aluno.nome_completo}. "
        f"Envie este link para o aluno: {link_atualizacao}"
    )
    
    # Redireciona de volta para o perfil do aluno
    return redirect('cadastros:perfil_aluno', pk=aluno.pk)


def atualizar_dados_aluno(request, token):
    """
    View pública que o aluno acessa para atualizar seus dados.
    """
    # Tenta encontrar um token que seja válido (não usado e não expirado)
    try:
        token_obj = TokenAtualizacaoAluno.objects.get(token=token, usado=False)
        if token_obj.is_expired:
            # Se o token expirou, renderiza uma página de erro
            return render(request, 'cadastros/token_invalido.html', {'motivo': 'Este link expirou.'})
    except TokenAtualizacaoAluno.DoesNotExist:
        # Se o token não existe ou já foi usado, renderiza uma página de erro
        return render(request, 'cadastros/token_invalido.html', {'motivo': 'Este link é inválido ou já foi utilizado.'})

    aluno = token_obj.aluno

    if request.method == 'POST':
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            form.save()
            # Marca o token como usado para que não possa ser utilizado novamente
            token_obj.usado = True
            token_obj.save()
            # Renderiza uma página de sucesso
            return render(request, 'cadastros/atualizacao_sucesso.html')
    else:
        # Se for um GET, exibe o formulário preenchido com os dados do aluno
        form = AlunoForm(instance=aluno)

    context = {
        'form': form,
        'aluno': aluno
    }
    return render(request, 'cadastros/atualizar_cadastro_form.html', context)

@login_required
def lista_acompanhamento_pedagogico(request):
    """
    Página principal do módulo, mostrando agendamentos, provas para corrigir e a lista de alunos.
    """
    agendamentos_pendentes = AcompanhamentoPedagogico.objects.filter(
        status='agendado'
    ).select_related('aluno', 'criado_por').order_by('data_agendamento')

    # ✅ NOVA CONSULTA PARA PROVAS AGUARDANDO CORREÇÃO ✅
    provas_para_corrigir = AlunoProva.objects.filter(
        status='aguardando_correcao'
    ).select_related('aluno', 'prova_template').order_by('data_realizacao')


    ultimo_acompanhamento_subquery = AcompanhamentoPedagogico.objects.filter(
        aluno=OuterRef('pk'), status='realizado'
    ).order_by('-data_realizacao').values('data_realizacao')[:1]

    
    turma_atual_subquery = Inscricao.objects.filter(
        aluno=OuterRef('pk'),
        status__in=['matriculado', 'experimental', 'acompanhando']
    ).values('turma__nome')[:1]

    
    alunos_list = Aluno.objects.filter(status='ativo').annotate(
        ultimo_acompanhamento=Subquery(ultimo_acompanhamento_subquery),
        turma_atual=Subquery(turma_atual_subquery)  
    ).order_by('nome_completo')

    context = {
        'agendamentos_pendentes': agendamentos_pendentes,
        'provas_para_corrigir': provas_para_corrigir, # <-- Enviando para o template
        'alunos': alunos_list,
    }
    return render(request, 'cadastros/lista_acompanhamento.html', context)


@login_required
def adicionar_acompanhamento(request, aluno_pk):
    """
    View para agendar ou registrar um novo acompanhamento para um aluno.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    
    if request.method == 'POST':
        form = AcompanhamentoPedagogicoForm(request.POST)
        if form.is_valid():
            acompanhamento = form.save(commit=False)
            acompanhamento.aluno = aluno
            try:
                # Tenta associar o professor que está logado
                acompanhamento.criado_por = Professor.objects.get(usuario=request.user)
            except Professor.DoesNotExist:
                # Se não for um professor, não associa ninguém (pode ser um admin)
                pass
            
            # Se a data de realização for preenchida, o status muda para 'realizado'
            if acompanhamento.data_realizacao:
                acompanhamento.status = 'realizado'

            acompanhamento.save()
            messages.success(request, f"Acompanhamento para {aluno.nome_completo} salvo com sucesso.")
            return redirect('cadastros:lista_acompanhamento_pedagogico')
    else:
        form = AcompanhamentoPedagogicoForm()

    context = {
        'form': form,
        'aluno': aluno,
    }
    return render(request, 'cadastros/form_acompanhamento.html', context)


@login_required
def editar_acompanhamento(request, pk):
    """
    View para editar um acompanhamento existente.
    """
    acompanhamento = get_object_or_404(AcompanhamentoPedagogico, pk=pk)
    aluno = acompanhamento.aluno

    if request.method == 'POST':
        form = AcompanhamentoPedagogicoForm(request.POST, instance=acompanhamento)
        if form.is_valid():
            acompanhamento = form.save(commit=False)
            # Se a data de realização for preenchida, o status muda para 'realizado'
            if acompanhamento.data_realizacao:
                acompanhamento.status = 'realizado'
            acompanhamento.save()

            messages.success(request, f"Acompanhamento de {aluno.nome_completo} atualizado com sucesso.")
            return redirect('cadastros:lista_acompanhamento_pedagogico')
    else:
        form = AcompanhamentoPedagogicoForm(instance=acompanhamento)
    
    context = {
        'form': form,
        'aluno': aluno,
        'acompanhamento': acompanhamento,
    }
    return render(request, 'cadastros/form_acompanhamento.html', context)

@login_required
def historico_acompanhamentos_aluno(request, aluno_pk):
    """
    Exibe o histórico completo de acompanhamentos pedagógicos de um aluno.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    
    # Busca todos os acompanhamentos do aluno, ordenados do mais recente para o mais antigo
    acompanhamentos = AcompanhamentoPedagogico.objects.filter(
        aluno=aluno
    ).select_related('criado_por').order_by('-data_agendamento')

    provas_do_aluno = AlunoProva.objects.filter(
        aluno=aluno
    ).select_related('prova_template').order_by('-data_realizacao')

    context = {
        'aluno': aluno,
        'acompanhamentos': acompanhamentos,
        'provas': provas_do_aluno
    }
    
    return render(request, 'cadastros/historico_acompanhamentos.html', context)

@login_required
def portal_aluno(request):
    """
    Página principal (dashboard) do Portal do Aluno.
    """
    try:
        aluno = request.user.perfil_aluno
    except Aluno.DoesNotExist:
        messages.error(request, "Acesso negado. Esta área é exclusiva para alunos.")
        return redirect('cadastros:dashboard_admin')

    # --- DADOS FINANCEIROS (já existentes) ---
    kpis_financeiros = Pagamento.objects.filter(aluno=aluno).aggregate(
        total_pendente=Sum('valor', filter=Q(status__in=['pendente', 'parcial', 'atrasado'])),
        total_atrasado=Sum('valor', filter=Q(status='atrasado')),
        contagem_atrasados=Count('id', filter=Q(status='atrasado'))
    )
    pagamentos_abertos = Pagamento.objects.filter(aluno=aluno, status__in=['pendente', 'parcial', 'atrasado']).order_by('data_vencimento')[:5]
    ultimos_pagos = Pagamento.objects.filter(aluno=aluno, status='pago').order_by('-data_pagamento')[:5]

    # --- ✅ NOVAS CONSULTAS DE FREQUÊNCIA ✅ ---
    hoje = timezone.now().date()
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    data_selecionada = date(ano_selecionado, mes_selecionado, 1)

    mes_anterior = (data_selecionada.month - 2 + 12) % 12 + 1
    ano_anterior = data_selecionada.year if data_selecionada.month > 1 else data_selecionada.year - 1
    mes_seguinte = data_selecionada.month % 12 + 1
    ano_seguinte = data_selecionada.year if data_selecionada.month < 12 else data_selecionada.year + 1

    # 1. Estatísticas Gerais de Frequência
    presencas_stats = Presenca.objects.filter(aluno=aluno).aggregate(
        total_aulas=Count('id'),
        total_presencas=Count('id', filter=Q(presente=True))
    )
    total_aulas = presencas_stats['total_aulas'] or 1
    percentual_frequencia = (presencas_stats['total_presencas'] / total_aulas) * 100

    # 2. Histórico das últimas 5 aulas
    historico_aulas_mes = Presenca.objects.filter(
        aluno=aluno,
        registro_aula__data_aula__year=ano_selecionado,
        registro_aula__data_aula__month=mes_selecionado
    ).select_related('registro_aula__turma').order_by('-registro_aula__data_aula')

    # 3. Dados para o gráfico de frequência (últimos 6 meses)
    meses_frequencia_data = []
    hoje = timezone.now().date()
    for i in range(5, -1, -1):
        mes_data = hoje - relativedelta(months=i)
        mes_inicio, mes_fim = mes_data.replace(day=1), (mes_data.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        
        presencas_mes = Presenca.objects.filter(
            aluno=aluno, registro_aula__data_aula__range=[mes_inicio, mes_fim]
        ).aggregate(total=Count('id'), presentes=Count('id', filter=Q(presente=True)))
        
        percentual_mes = (presencas_mes['presentes'] / presencas_mes['total'] * 100) if presencas_mes['total'] > 0 else 0
        
        meses_frequencia_data.append({
            'mes': mes_inicio.strftime('%b/%Y'),
            'percentual': round(percentual_mes, 1),
        })

    provas_aluno = AlunoProva.objects.filter(
        aluno=aluno
    ).select_related('prova_template').order_by('-data_realizacao')
    
    provas_pendentes = provas_aluno.filter(status='nao_iniciada')
    provas_finalizadas = provas_aluno.filter(status='finalizada')

    context = {
        'aluno': aluno,
        'kpis': kpis_financeiros,
        'pagamentos_abertos': pagamentos_abertos,
        'ultimos_pagos': ultimos_pagos,
        'percentual_frequencia': percentual_frequencia,
        'historico_aulas': historico_aulas_mes, # <-- Usando a nova variável
        'meses_frequencia': meses_frequencia_data,
        'data_selecionada': data_selecionada, # <-- Nova variável para o template
        'provas_pendentes': provas_pendentes,
        'provas_finalizadas': provas_finalizadas,
        'nav': { # <-- Nova variável para a navegação
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        }
    }
    return render(request, 'cadastros/portal_aluno.html', context)

@login_required
@require_POST # Garante que esta ação só pode ser feita via POST, por segurança
def criar_acesso_portal(request, aluno_pk):
    """
    Cria um User do Django para um Aluno que ainda não tem acesso ao portal.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)

    if aluno.usuario:
        messages.warning(request, f"O aluno {aluno.nome_completo} já possui um acesso ao portal.")
        return redirect('cadastros:perfil_aluno', pk=aluno.pk)

    username = aluno.email or re.sub(r'\D', '', aluno.cpf or '') or f"aluno{aluno.pk}"
    if User.objects.filter(username=username).exists():
        username = f"{username}{aluno.pk}"

    # ✅ LINHA CORRIGIDA ✅
    # Usamos get_random_string para gerar uma palavra-passe aleatória de 8 caracteres.
    password = get_random_string(length=8)

    try:
        novo_usuario = User.objects.create_user(username=username, password=password)
        aluno.usuario = novo_usuario
        aluno.save()

        messages.success(
            request,
            f"Acesso ao portal criado para {aluno.nome_completo}. "
            f"Envie as seguintes credenciais para o aluno de forma segura: "
            f"Utilizador: {username} | Palavra-passe Temporária: {password}"
        )
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao criar o acesso: {e}")

    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

def portal_login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # A MÁGICA ACONTECE AQUI: Verificamos o tipo de utilizador
                if hasattr(user, 'professor'):
                    # Se for um professor, vai para o portal do professor
                    return redirect('cadastros:portal_professor')
                elif hasattr(user, 'perfil_aluno'):
                    # Se for um aluno, vai para o portal do aluno
                    return redirect('cadastros:portal_aluno')
                else:
                    # Se for outro tipo de user (ex: admin), vai para o dashboard
                    return redirect('cadastros:dashboard_admin')
        else:
            messages.error(request, "Nome de utilizador ou palavra-passe inválidos.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'cadastros/portal_login.html', {'form': form})

login_required
@require_POST
def redefinir_senha_aluno(request, aluno_pk):
    """
    Redefine a senha de um Aluno que já possui um User, gerando uma nova senha temporária.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)

    if not aluno.usuario:
        messages.error(request, "Este aluno ainda não possui um acesso ao portal para que a senha seja redefinida.")
        return redirect('cadastros:perfil_aluno', pk=aluno.pk)

    # Gera uma nova palavra-passe aleatória e segura
    nova_senha = get_random_string(length=8)
    
    try:
        usuario = aluno.usuario
        usuario.set_password(nova_senha) # Define a nova senha de forma segura (com hash)
        usuario.save()

        messages.success(
            request,
            f"Senha redefinida para {aluno.nome_completo}. "
            f"As novas credenciais são: "
            f"Utilizador: {usuario.username} | Nova Senha Temporária: {nova_senha}"
        )
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao redefinir a senha: {e}")

    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

@login_required
def iniciar_prova(request, aluno_prova_pk):
    """
    Ponto de entrada para uma prova. Verifica as condições e redireciona para a primeira secção.
    """
    aluno_prova = get_object_or_404(AlunoProva, pk=aluno_prova_pk, aluno__usuario=request.user)
    
    # Mudar status para "Em Progresso"
    if aluno_prova.status == 'nao_iniciada':
        aluno_prova.status = 'em_progresso'
        aluno_prova.save()

    # Redireciona para a primeira secção da prova
    return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=1)


@login_required
def realizar_prova_secao(request, aluno_prova_pk, secao_num):
    # ... (a lógica inicial da view continua a mesma)
    aluno_prova = get_object_or_404(AlunoProva, pk=aluno_prova_pk, aluno__usuario=request.user)
    prova_template = aluno_prova.prova_template
    ordem_sessoes = prova_template.ordem_sessoes
    
    if secao_num > len(ordem_sessoes):
        # ... (a lógica de finalização da prova continua a mesma)
        if aluno_prova.status != 'finalizada':
            aluno_prova.status = 'aguardando_correcao'
            aluno_prova.save()
        return redirect('cadastros:prova_concluida', aluno_prova_pk=aluno_prova.pk)

    tipo_secao_atual = ordem_sessoes[secao_num - 1]
    questoes_da_secao = Questao.objects.filter(
        prova_template=prova_template, tipo_questao=tipo_secao_atual
    ).order_by('ordem')
    
    # ✅ LÓGICA ADICIONADA PARA BUSCAR A INSTRUÇÃO DA SECÇÃO ✅
    instrucao_da_secao = prova_template.instrucoes_sessoes.get(tipo_secao_atual, "")

    # ... (a lógica de formulário dinâmico e POST continua a mesma) ...
    respostas_qs = RespostaAluno.objects.filter(aluno_prova=aluno_prova, questao__in=questoes_da_secao)
    respostas_anteriores = {resposta.questao_id: resposta for resposta in respostas_qs}
    form_fields = {}
    for questao in questoes_da_secao:
        # ... (criação dos campos do formulário)
        field_name = f'questao_{questao.pk}'
        initial_value = ''
        resposta_obj = respostas_anteriores.get(questao.pk)
        if questao.tipo_questao in ['dictation', 'error_correction', 'gap_fill', 'dissertativa']:
            if resposta_obj: initial_value = resposta_obj.resposta_texto
            widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 4}) if questao.tipo_questao in ['dictation', 'dissertativa'] else forms.TextInput(attrs={'class': 'form-control'})
            form_fields[field_name] = forms.CharField(label=f"Q{questao.ordem}: {questao.enunciado}", required=False, widget=widget, initial=initial_value)
        elif questao.tipo_questao in ['yes_no', 'multiple_choice', 'oral_multiple_choice']:
            if resposta_obj: initial_value = resposta_obj.resposta_opcao
            opcoes = list(questao.dados_questao.get('opcoes', {}).items()) if questao.tipo_questao != 'yes_no' else [('sim', 'Sim'), ('nao', 'Não')]
            form_fields[field_name] = forms.ChoiceField(label=f"Q{questao.ordem}: {questao.enunciado}", choices=opcoes, widget=forms.RadioSelect, required=False, initial=initial_value)
    ProvaSecaoForm = type('ProvaSecaoForm', (forms.Form,), form_fields)
    
    if request.method == 'POST':
        # ... (lógica do POST)
        form = ProvaSecaoForm(request.POST)
        if form.is_valid():
            for questao in questoes_da_secao:
                field_name = f'questao_{questao.pk}'
                resposta_dada = form.cleaned_data.get(field_name, '')
                resposta_a_guardar = {}
                if questao.tipo_questao in ['dictation', 'error_correction', 'gap_fill', 'dissertativa']:
                    resposta_a_guardar['resposta_texto'] = resposta_dada
                else:
                    resposta_a_guardar['resposta_opcao'] = resposta_dada
                RespostaAluno.objects.update_or_create(aluno_prova=aluno_prova, questao=questao, defaults=resposta_a_guardar)
            return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=secao_num + 1)
    else:
        form = ProvaSecaoForm()

    context = {
        'aluno_prova': aluno_prova,
        'form': form,
        'secao_atual_num': secao_num,
        'secao_atual_titulo': dict(Questao.TIPO_QUESTAO_CHOICES).get(tipo_secao_atual),
        'total_secoes': len(ordem_sessoes),
        'proxima_secao_num': secao_num + 1,
        'instrucao_da_secao': instrucao_da_secao, # <-- ✅ ENVIANDO A INSTRUÇÃO PARA O TEMPLATE
    }
    return render(request, 'cadastros/realizar_prova.html', context)

@login_required
def prova_concluida(request, aluno_prova_pk):
    """
    Página simples de confirmação de que a prova foi enviada.
    """
    aluno_prova = get_object_or_404(AlunoProva, pk=aluno_prova_pk, aluno__usuario=request.user)
    context = {
        'aluno_prova': aluno_prova
    }
    return render(request, 'cadastros/prova_concluida.html', context)

@login_required
def realizar_prova_secao(request, aluno_prova_pk, secao_num):
    """
    View principal que controla a exibição e o salvamento de cada secção da prova.
    """
    aluno_prova = get_object_or_404(AlunoProva, pk=aluno_prova_pk, aluno__usuario=request.user)
    prova_template = aluno_prova.prova_template
    ordem_sessoes = prova_template.ordem_sessoes
    
    if secao_num > len(ordem_sessoes):
        if aluno_prova.status != 'finalizada':
            aluno_prova.status = 'aguardando_correcao'
            aluno_prova.save()
        return redirect('cadastros:prova_concluida', aluno_prova_pk=aluno_prova.pk)

    tipo_secao_atual = ordem_sessoes[secao_num - 1]
    questoes_da_secao = Questao.objects.filter(
        prova_template=prova_template, tipo_questao=tipo_secao_atual
    ).order_by('ordem')

    # --- LÓGICA DE FORMULÁRIO DINÂMICO ---
    
    # ✅ --- BLOCO CORRIGIDO --- ✅
    # Em vez de .in_bulk(), buscamos o queryset e criamos o dicionário em Python.
    respostas_qs = RespostaAluno.objects.filter(
        aluno_prova=aluno_prova, questao__in=questoes_da_secao
    )
    respostas_anteriores = {resposta.questao_id: resposta for resposta in respostas_qs}
    # ✅ --- FIM DO BLOCO CORRIGIDO --- ✅

    form_fields = {}
    for questao in questoes_da_secao:
        field_name = f'questao_{questao.pk}'
        initial_value = ''
        resposta_obj = respostas_anteriores.get(questao.pk)

        if questao.tipo_questao in ['dictation', 'error_correction', 'gap_fill', 'dissertativa']:
            if resposta_obj: initial_value = resposta_obj.resposta_texto
            widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 4}) if questao.tipo_questao in ['dictation', 'dissertativa'] else forms.TextInput(attrs={'class': 'form-control'})
            form_fields[field_name] = forms.CharField(label=f"Q{questao.ordem}: {questao.enunciado}", required=False, widget=widget, initial=initial_value)
        
        elif questao.tipo_questao in ['yes_no', 'multiple_choice', 'oral_multiple_choice']:
            if resposta_obj: initial_value = resposta_obj.resposta_opcao
            opcoes = list(questao.dados_questao.get('opcoes', {}).items()) if questao.tipo_questao != 'yes_no' else [('yes', 'Yes'), ('no', 'No')]
            form_fields[field_name] = forms.ChoiceField(label=f"Q{questao.ordem}: {questao.enunciado}", choices=opcoes, widget=forms.RadioSelect, required=False, initial=initial_value)
    
    ProvaSecaoForm = type('ProvaSecaoForm', (forms.Form,), form_fields)
    
    if request.method == 'POST':
        form = ProvaSecaoForm(request.POST)
        if form.is_valid():
            for questao in questoes_da_secao:
                field_name = f'questao_{questao.pk}'
                resposta_dada = form.cleaned_data.get(field_name, '')
                
                resposta_a_guardar = {}
                if questao.tipo_questao in ['dictation', 'error_correction', 'gap_fill', 'dissertativa']:
                    resposta_a_guardar['resposta_texto'] = resposta_dada
                else:
                    resposta_a_guardar['resposta_opcao'] = resposta_dada

                RespostaAluno.objects.update_or_create(
                    aluno_prova=aluno_prova,
                    questao=questao,
                    defaults=resposta_a_guardar
                )
            
            return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=secao_num + 1)
    else:
        form = ProvaSecaoForm()

    context = {
        'aluno_prova': aluno_prova,
        'form': form,
        'secao_atual_num': secao_num,
        'secao_atual_titulo': dict(Questao.TIPO_QUESTAO_CHOICES).get(tipo_secao_atual),
        'total_secoes': len(ordem_sessoes),
        'proxima_secao_num': secao_num + 1,
    }
    return render(request, 'cadastros/realizar_prova.html', context)

@login_required
def liberar_prova(request, aluno_pk):
    """
    View para um professor 'liberar' uma ProvaTemplate para um aluno,
    criando uma instância de AlunoProva.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    
    if request.method == 'POST':
        form = LiberarProvaForm(request.POST)
        if form.is_valid():
            prova_template_selecionada = form.cleaned_data['prova_template']
            
            # Cria a instância da prova para o aluno
            aluno_prova = AlunoProva.objects.create(
                aluno=aluno,
                prova_template=prova_template_selecionada,
                # O status 'nao_iniciada' é o default do modelo
            )
            
            messages.success(request, f'Prova "{prova_template_selecionada.titulo}" liberada para {aluno.nome_completo}.')
            # Redireciona para o histórico, onde a nova prova aparecerá
            return redirect('cadastros:historico_acompanhamentos_aluno', aluno_pk=aluno.pk)
    else:
        form = LiberarProvaForm()

    context = {
        'form': form,
        'aluno': aluno,
    }
    return render(request, 'cadastros/liberar_prova.html', context)

@login_required
def liberar_prova_turma(request, turma_pk):
    """
    View para um professor 'liberar' uma ProvaTemplate para todos os alunos
    de uma turma específica.
    """
    turma = get_object_or_404(Turma, pk=turma_pk)
    
    if request.method == 'POST':
        form = LiberarProvaForm(request.POST)
        if form.is_valid():
            prova_template_selecionada = form.cleaned_data['prova_template']
            
            # Encontra todos os alunos matriculados na turma
            inscricoes = Inscricao.objects.filter(turma=turma, status='matriculado')
            
            # Cria uma instância de AlunoProva para cada aluno
            for inscricao in inscricoes:
                AlunoProva.objects.get_or_create(
                    aluno=inscricao.aluno,
                    prova_template=prova_template_selecionada,
                    defaults={'status': 'nao_iniciada'} # Só cria se não existir
                )
            
            messages.success(request, f'Prova "{prova_template_selecionada.titulo}" liberada para {inscricoes.count()} aluno(s) da turma {turma.nome}.')
            return redirect('cadastros:detalhe_turma', pk=turma.pk)
    else:
        form = LiberarProvaForm()

    context = {
        'form': form,
        'turma': turma,
    }
    # Usaremos o mesmo template de liberar prova, mas com contexto de turma
    return render(request, 'cadastros/liberar_prova.html', context)

@login_required
def corrigir_prova(request, aluno_prova_pk):
    aluno_prova = get_object_or_404(AlunoProva.objects.select_related('aluno', 'prova_template'), pk=aluno_prova_pk)
    
    if aluno_prova.status == 'finalizada':
        messages.info(request, "Esta prova já foi corrigida e finalizada.")
        return redirect('cadastros:lista_acompanhamento_pedagogico')

    prova_template = aluno_prova.prova_template
    ordem_sessoes = prova_template.ordem_sessoes
    
    respostas_qs = RespostaAluno.objects.filter(aluno_prova=aluno_prova)
    respostas_map = {resposta.questao_id: resposta for resposta in respostas_qs}

    if request.method == 'POST':
        nota_total = Decimal('0.0')
        questoes_todas = Questao.objects.filter(prova_template=prova_template)

        # ✅ 1. CALCULA A PONTUAÇÃO MÁXIMA POSSÍVEL DA PROVA ✅
        pontuacao_maxima = questoes_todas.aggregate(total=Sum('pontos'))['total'] or Decimal('0.0')

        for questao in questoes_todas:
            resposta = respostas_map.get(questao.id)
            if not resposta: continue

            pontos_str = request.POST.get(f'pontos_{questao.id}', '0').replace(',', '.')
            pontos = Decimal(pontos_str)
            feedback = request.POST.get(f'feedback_{questao.id}', '')

            resposta.pontos_obtidos = pontos
            resposta.feedback_professor = feedback
            resposta.corrigido = True
            resposta.save()
            
            nota_total += pontos
        
        aluno_prova.nota_final = nota_total
        aluno_prova.status = 'finalizada'
        
        # ✅ 2. SALVA A PONTUAÇÃO MÁXIMA NO REGISTO DA PROVA ✅
        aluno_prova.pontuacao_total = pontuacao_maxima

        if hasattr(request.user, 'professor'):
            aluno_prova.corrigido_por = request.user.professor
        aluno_prova.save()
        
        messages.success(request, f"Prova de {aluno_prova.aluno.nome_completo} corrigida com sucesso!")
        return redirect('cadastros:lista_acompanhamento_pedagogico')

    # (A lógica GET para exibir o formulário de correção continua a mesma)
    secoes_para_correcao = []
    for tipo_secao in ordem_sessoes:
        questoes_da_secao = Questao.objects.filter(
            prova_template=prova_template, tipo_questao=tipo_secao
        ).order_by('ordem')
        
        dados_da_secao = {
            'titulo': dict(Questao.TIPO_QUESTAO_CHOICES).get(tipo_secao),
            'questoes': []
        }
        for questao in questoes_da_secao:
            dados_da_secao['questoes'].append({
                'questao': questao,
                'resposta': respostas_map.get(questao.id)
            })
        secoes_para_correcao.append(dados_da_secao)

    context = {
        'aluno_prova': aluno_prova,
        'secoes_para_correcao': secoes_para_correcao,
    }
    return render(request, 'cadastros/corrigir_prova.html', context)


@login_required
def ver_resultado_prova(request, aluno_prova_pk):
    """
    Página para o aluno ou professor ver o resultado detalhado de uma prova finalizada.
    """
    aluno_prova = get_object_or_404(
        AlunoProva.objects.select_related('aluno', 'prova_template'), 
        pk=aluno_prova_pk, 
        status='finalizada'
    )
    
    if not (hasattr(request.user, 'professor') or aluno_prova.aluno.usuario == request.user):
        messages.error(request, "Você não tem permissão para ver este resultado.")
        return redirect('cadastros:portal_aluno' if hasattr(request.user, 'perfil_aluno') else 'cadastros:portal_professor')

    # ✅ LÓGICA DE SEGURANÇA PARA PONTUAÇÃO TOTAL ✅
    # Se a pontuação total não foi guardada (para provas antigas), calcula-a agora para exibição.
    if aluno_prova.pontuacao_total is None:
        pontuacao_maxima = aluno_prova.prova_template.questoes.aggregate(total=Sum('pontos'))['total'] or Decimal('0.0')
        aluno_prova.pontuacao_total = pontuacao_maxima
        # Não salvamos no banco de dados aqui para não modificar dados num GET,
        # apenas garantimos que o valor seja exibido no template.

    # Reutiliza a mesma lógica de agrupamento por secção
    ordem_sessoes = aluno_prova.prova_template.ordem_sessoes
    respostas_qs = RespostaAluno.objects.filter(aluno_prova=aluno_prova)
    respostas_map = {resposta.questao_id: resposta for resposta in respostas_qs}
    
    secoes_resultado = []
    for tipo_secao in ordem_sessoes:
        questoes_da_secao = Questao.objects.filter(
            prova_template=aluno_prova.prova_template, tipo_questao=tipo_secao
        ).order_by('ordem')
        
        dados_da_secao = { 'titulo': dict(Questao.TIPO_QUESTAO_CHOICES).get(tipo_secao), 'questoes': [] }
        for questao in questoes_da_secao:
            dados_da_secao['questoes'].append({
                'questao': questao,
                'resposta': respostas_map.get(questao.id)
            })
        secoes_resultado.append(dados_da_secao)

    context = {
        'aluno_prova': aluno_prova,
        'secoes_resultado': secoes_resultado,
    }
    return render(request, 'cadastros/ver_resultado_prova.html', context)

@login_required
def copiar_prova_template(request, pk):
    """
    Cria uma cópia de um ProvaTemplate existente e de todas as suas Questões associadas.
    """
    try:
        original_template = ProvaTemplate.objects.get(pk=pk)
        questoes_originais = list(original_template.questoes.all())

        with transaction.atomic():
            # Clona o ProvaTemplate
            novo_template = original_template
            novo_template.pk = None  # Força a criação de um novo objeto
            novo_template.titulo = f"{original_template.titulo} (Cópia)"
            novo_template.save()

            # Clona todas as Questões associadas
            for questao in questoes_originais:
                nova_questao = questao
                nova_questao.pk = None
                nova_questao.prova_template = novo_template
                nova_questao.save()
        
        messages.success(request, f'O gabarito "{original_template.titulo}" foi copiado com sucesso. Agora você está a editar a cópia.')
        # Redireciona para a página de edição do NOVO template no admin
        return redirect(reverse('admin:cadastros_provatemplate_change', args=[novo_template.pk]))

    except ProvaTemplate.DoesNotExist:
        messages.error(request, "O gabarito de prova que tentou copiar não existe.")
    except Exception as e:
        messages.error(request, f"Ocorreu um erro inesperado ao copiar o gabarito: {e}")
    
    return redirect(reverse('admin:cadastros_provatemplate_changelist'))