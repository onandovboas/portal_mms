# cadastros/views.py
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Turma, Inscricao, RegistroAula, Professor, Presenca, Pagamento, Contrato, AcompanhamentoFalta, Aluno, Inscricao, RegistroAula, Presenca, Lead, TokenAtualizacaoAluno, AcompanhamentoPedagogico, AlunoProva, Questao, ProvaTemplate, RespostaAluno, PesquisaSatisfacao, AvaliacaoProfessor, AvaliacaoAdministrativo, AvaliacaoPedagogico
from .forms import (
    AlunoForm, PagamentoForm, AlunoExperimentalForm, ContratoForm, 
    RegistroAulaForm, LeadForm, AcompanhamentoPedagogicoForm, 
    LiberarProvaForm, PlanoAulaForm, PesquisaSatisfacaoForm, EsqueciSenhaForm
)
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
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.db.models.functions import ExtractWeek
from django.contrib.auth.models import User # <-- Adicione este import
import re
from django.utils.crypto import get_random_string
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.contrib.auth import views as auth_views
from django import forms
from django.db import transaction
from django.utils.html import format_html
import json
import io
import zipfile
from .decorators import admin_required, professor_required, aluno_required
from django.db.models import Avg, FloatField, Case, When
from django.db.models.functions import Cast
from collections import Counter
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .forms import EnviarEmailForm



# --- Views do Portal do Professor ---

@login_required
@professor_required
def portal_professor(request):
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
@professor_required
def detalhe_turma(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    hoje = timezone.now().date() # Definido 'hoje' no topo

    # =====================================================
    # CORREÇÃO 1: Lógica POST unificada num só bloco
    # =====================================================
    if request.method == 'POST':
        # Tenta buscar o professor logado primeiro
        try:
            professor = Professor.objects.get(usuario=request.user)
        except Professor.DoesNotExist:
            # Se não for professor (ex: admin), define como None
            professor = None
        
        # --- Lógica para 'salvar_aula' (Aula de Hoje) ---
        if 'salvar_aula' in request.POST:
            
            # 1. Procura se já existe um plano para hoje
            novo_registro = RegistroAula.objects.filter(turma=turma, data_aula=hoje).first()

            dados_aula = {
                'turma': turma,
                'professor': professor, # Usa o professor logado
                'data_aula': hoje,
                'last_word': request.POST.get('last_word'),
                'last_parag': request.POST.get('last_parag') or None,
                'new_dictation': request.POST.get('new_dictation') or None,
                'old_dictation': request.POST.get('old_dictation') or None,
                'new_reading': request.POST.get('new_reading') or None,
                'old_reading': request.POST.get('old_reading') or None,
                'lesson_check': request.POST.get('lesson_check'),
            }
            
            if novo_registro:
                # 2. Se existe (era um plano), ATUALIZA
                for key, value in dados_aula.items():
                    setattr(novo_registro, key, value)
                novo_registro.save()
            else:
                # 3. Se não existe, CRIA
                novo_registro = RegistroAula.objects.create(**dados_aula)

            # 4. A lógica de presença é executada DEPOIS
            alunos_presentes_ids = request.POST.getlist('presenca')
            todos_os_inscritos = list(turma.inscricao_set.filter(status__in=['matriculado', 'experimental', 'acompanhando']))
            
            Presenca.objects.filter(registro_aula=novo_registro).delete() # Limpa presenças antigas, se houver
            
            for inscricao in todos_os_inscritos:
                Presenca.objects.create(
                    registro_aula=novo_registro, aluno=inscricao.aluno,
                    presente=(str(inscricao.aluno.pk) in alunos_presentes_ids)
                )

        # --- Lógica para 'salvar_aula_atrasada' ---
        elif 'salvar_aula_atrasada' in request.POST:
            professor_id = request.POST.get('professor_aula_atrasada')

            try:
                professor_selecionado = Professor.objects.get(pk=professor_id)
            except (Professor.DoesNotExist, ValueError): # <--- CORREÇÃO AQUI
                messages.error(request, 'Você deve selecionar um professor válido.')
                return redirect('cadastros:detalhe_turma', pk=turma.pk)

            data_aula_str = request.POST.get('data_aula_atrasada')
            if not data_aula_str:
                messages.error(request, 'A data da aula é obrigatória.')
                return redirect('cadastros:detalhe_turma', pk=turma.pk)

            novo_registro = RegistroAula.objects.create(
                turma=turma, 
                professor=professor_selecionado, # <-- Usa o professor do formulário
                data_aula=data_aula_str,
                last_word=request.POST.get('last_word_atrasada'),
                last_parag=request.POST.get('last_parag_atrasada') or None,
                new_dictation=request.POST.get('new_dictation_atrasada') or None,
                old_dictation=request.POST.get('old_dictation_atrasada') or None,
                new_reading=request.POST.get('new_reading_atrasada') or None,
                old_reading=request.POST.get('old_reading_atrasada') or None,
                lesson_check=request.POST.get('lesson_check_atrasada'),
            )
            
            alunos_presentes_ids = request.POST.getlist('presenca_atrasada')
            todos_os_inscritos = list(turma.inscricao_set.filter(status__in=['matriculado', 'experimental', 'acompanhando']))
            for inscricao in todos_os_inscritos:
                Presenca.objects.create(
                    registro_aula=novo_registro, aluno=inscricao.aluno,
                    presente=(str(inscricao.aluno.pk) in alunos_presentes_ids)
                )
        
        # --- Lógica para 'salvar_plano_aula' ---
        elif 'salvar_plano_aula' in request.POST:
            form_plano_aula = PlanoAulaForm(request.POST) # Define a variável no POST
            if form_plano_aula.is_valid():
                data_planejada = form_plano_aula.cleaned_data['data_aula']
                if data_planejada <= hoje:
                    messages.error(request, 'A data do planejamento deve ser no futuro.')
                else:
                    plano = RegistroAula.objects.filter(turma=turma, data_aula=data_planejada).first()
                    if not plano:
                        plano = form_plano_aula.save(commit=False)
                    else:
                        plano.last_parag = form_plano_aula.cleaned_data['last_parag']
                        plano.last_word = form_plano_aula.cleaned_data['last_word']
                        plano.new_dictation = form_plano_aula.cleaned_data['new_dictation']
                        plano.old_dictation = form_plano_aula.cleaned_data['old_dictation']
                        plano.new_reading = form_plano_aula.cleaned_data['new_reading']
                        plano.old_reading = form_plano_aula.cleaned_data['old_reading']
                        plano.lesson_check = form_plano_aula.cleaned_data['lesson_check']

                    plano.turma = turma
                    plano.professor = professor # Usa o professor logado
                    plano.save()
                    messages.success(request, f'Aula para {data_planejada.strftime("%d/%m/%Y")} planejada com sucesso.')
            else:
                messages.error(request, 'Erro no formulário de planejamento. Verifique os dados.')

        # --- Lógica para 'salvar_detalhes_turma' ---
        elif 'salvar_detalhes_turma' in request.POST:
            novo_nome = request.POST.get('nome_turma')
            novo_stage = request.POST.get('stage_turma')
            if novo_nome:
                turma.nome = novo_nome
            if novo_stage:
                turma.stage = novo_stage
            turma.save()
        
        elif 'salvar_anotacoes' in request.POST:
            anotacoes = request.POST.get('anotacoes_gerais')
            turma.anotacoes_gerais = anotacoes
            turma.save()
            messages.success(request, 'Anotações da turma salvas com sucesso.')

        # Redireciona no final de qualquer ação POST
        return redirect('cadastros:detalhe_turma', pk=turma.pk)

    # --- INÍCIO DA LÓGICA GET ---
    # (Ocorre se request.method != 'POST')

    plano_de_hoje = RegistroAula.objects.filter(turma=turma, data_aula=hoje).first()
    aulas_planejadas = RegistroAula.objects.filter(
        turma=turma, 
        data_aula__gt=hoje
    ).select_related('professor').order_by('data_aula')

    alunos_da_turma_ids = Inscricao.objects.filter(turma=turma).values_list('aluno_id', flat=True)
    provas_da_turma = AlunoProva.objects.filter(
        aluno_id__in=alunos_da_turma_ids
    ).select_related('aluno', 'prova_template').order_by('-data_realizacao')

    ano_selecionado = int(request.GET.get('ano', hoje.year))
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    data_atual = date(ano_selecionado, mes_selecionado, 1)

    historico_aulas = RegistroAula.objects.filter(
        turma=turma,
        data_aula__year=ano_selecionado, 
        data_aula__month=mes_selecionado,
        data_aula__lte=hoje
    ).select_related('professor').prefetch_related(
        'presenca_set__aluno'
    ).annotate(
        # 1. Contamos quantos registos de presença CADA aula tem
        presenca_count=Count('presenca')
    ).filter(
        # 2. Filtramos para mostrar APENAS aulas que têm 1 ou mais registos de presença
        presenca_count__gt=0
    ).order_by('-data_aula')
    
    todos_professores = Professor.objects.all().order_by('nome_completo')

    alunos_ativos_na_turma = Aluno.objects.filter(
        inscricao__turma=turma, 
        inscricao__status__in=['matriculado', 'experimental', 'acompanhando']
    ).distinct()
    
    mapa_alunos_ativos = {aluno.pk: aluno for aluno in alunos_ativos_na_turma}
    set_ids_alunos_ativos = set(mapa_alunos_ativos.keys())

    for aula in historico_aulas:
        aula.alunos_ausentes = [
            p.aluno.nome_completo.split(' ')[0]
            for p in aula.presenca_set.all() 
            if not p.presente
        ]

    faltas_do_mes = Presenca.objects.filter(
        registro_aula__turma=turma,
        registro_aula__data_aula__year=ano_selecionado,
        registro_aula__data_aula__month=mes_selecionado,
        presente=False
    ).values(
        'aluno__nome_completo'
    ).annotate(
        total_faltas=Count('id')
    ).order_by('-total_faltas')

    # Lógica de navegação de meses
    mes_anterior = (data_atual.month - 2 + 12) % 12 + 1
    ano_anterior = data_atual.year if data_atual.month > 1 else data_atual.year - 1
    mes_seguinte = data_atual.month % 12 + 1
    ano_seguinte = data_atual.year if data_atual.month < 12 else data_atual.year + 1
    
    # Listas de alunos separadas por status
    inscritos_matriculados = Inscricao.objects.filter(turma=turma, status='matriculado')
    inscritos_experimentais = Inscricao.objects.filter(turma=turma, status='experimental')
    inscritos_acompanhando = Inscricao.objects.filter(turma=turma, status='acompanhando')
    inscritos_trancados = Inscricao.objects.filter(turma=turma, status='trancado')
    
    # =====================================================
    # CORREÇÃO 2: Definir 'form_plano_aula' para o GET
    # =====================================================
    form_plano_aula = PlanoAulaForm()
    
    context = {
        'turma': turma,
        'matriculados': inscritos_matriculados,
        'aulas_do_mes': historico_aulas,
        'experimentais': inscritos_experimentais,
        'acompanhando': inscritos_acompanhando,
        'trancados': inscritos_trancados,
        'plano_de_hoje': plano_de_hoje,
        'aulas_planejadas': aulas_planejadas,
        'form_plano_aula': form_plano_aula, # <-- Agora esta linha é válida
        'faltas_do_mes': faltas_do_mes,
        'historico_aulas': historico_aulas, # (Variável duplicada, mas ok)
        'data_selecionada': data_atual,
        'provas_da_turma': provas_da_turma,
        'todos_professores': todos_professores,
        'nav': {
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        }
    }
    return render(request, 'cadastros/detalhe_turma.html', context)


# --- Views do Dashboard do Administrador ---


@login_required
@admin_required
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
@admin_required
@professor_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def perfil_aluno(request, pk):
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

    contrato_ativo = (Contrato.objects
                      .filter(aluno=aluno, ativo=True)
                      .filter(Q(data_fim__gte=timezone.now()) | Q(data_fim__isnull=True))
                      .order_by('-data_inicio')
                      .first())

    historico_turmas = (Inscricao.objects
                        .filter(aluno=aluno)
                        .select_related('turma')
                        .order_by('-id'))

    acompanhamentos = (AcompanhamentoFalta.objects
                       .filter(aluno=aluno)
                       .order_by('-criado_em'))

    # Estatísticas simples de KPI
    presencas_stats = Presenca.objects.filter(aluno=aluno).aggregate(
        total_aulas=Count('id'),
        total_presencas=Count('id', filter=Q(presente=True))
    )
    total_aulas = presencas_stats['total_aulas'] or 1
    percentual_frequencia = (presencas_stats['total_presencas'] / total_aulas) * 100

    pagamentos = (Pagamento.objects.filter(aluno=aluno).order_by('-data_vencimento'))
    kpis = pagamentos.aggregate(
        pendentes=Count('id', filter=Q(status='pendente')),
        atrasados=Count('id', filter=Q(status='atrasado')),
    )

    # --- LÓGICA DO GRÁFICO HÍBRIDO (BARRAS + LINHA) ---
    dados_grafico = []
    hoje = timezone.now().date()
    
    for i in range(5, -1, -1):
        mes_data = hoje - relativedelta(months=i)
        mes_inicio = mes_data.replace(day=1)
        # Último dia do mês
        mes_fim = mes_inicio + relativedelta(months=1) - timedelta(days=1)
        
        # 1. Frequência (Barras)
        presencas_mes = Presenca.objects.filter(
            aluno=aluno,
            registro_aula__data_aula__range=[mes_inicio, mes_fim]
        ).aggregate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True))
        )
        total_m = presencas_mes['total'] or 0
        pres_m = presencas_mes['presentes'] or 0
        freq_pct = (pres_m / total_m * 100) if total_m > 0 else 0
        
        # 2. Notas (Linha) - Média percentual das provas do mês
        # Calculamos (nota_final / pontuacao_total * 100) para cada prova e tiramos a média
        provas_mes = AlunoProva.objects.filter(
            aluno=aluno,
            data_realizacao__range=[mes_inicio, mes_fim],
            status='finalizada'
        ).aggregate(media=Avg('nota_final'))
        
        # Se não houver provas, a média vem None, então tratamos para 0 ou None
        nota_media = provas_mes['media'] if provas_mes['media'] is not None else 0

        dados_grafico.append({
            'mes': mes_inicio.strftime('%b'),
            'freq': round(freq_pct, 1),
            'nota': round(float(nota_media), 1) # Convertemos Decimal para float para o JSON
        })

    # Todas as turmas para o modal de adicionar
    todas_turmas = Turma.objects.all().order_by('nome')

    context = {
        'aluno': aluno,
        'contrato_ativo': contrato_ativo,
        'historico_turmas': historico_turmas,
        'acompanhamentos': acompanhamentos,
        'presencas_stats': presencas_stats,
        'percentual_frequencia': percentual_frequencia,
        'pagamentos': pagamentos,
        'kpis': kpis,
        # Convertemos para JSON string para o JS ler sem erro
        'dados_grafico': json.dumps(dados_grafico), 
        'todas_turmas': todas_turmas,
    }

    return render(request, 'cadastros/perfil_aluno.html', context)

@login_required
@admin_required
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
@admin_required
def novo_pagamento(request, pk):
    """
    Atalho: redireciona para o formulário de lançamento existente,
    pré-selecionando o aluno via querystring e definindo 'next' para voltar ao perfil.
    """
    # se você já tem a rota 'lancamento_recebimento' no urls do projeto, isso funciona:
    next_url = reverse('cadastros:perfil_aluno', args=[pk]) if request.resolver_match.namespace == 'cadastros' else reverse('perfil_aluno', args=[pk])
    lancamento_url = reverse('cadastros:lancamento_recebimento')  # essa rota está no urls do projeto raiz
    return HttpResponseRedirect(f"{lancamento_url}?aluno={pk}&next={next_url}")



@login_required
@admin_required
def formulario_inscricao(request):
    # Por enquanto, esta view apenas exibe a página.
    # A lógica para salvar os dados virá depois.
    if request.method == 'POST':
        # Ação de salvar os dados virá aqui.
        pass

    return render(request, 'cadastros/inscricao_form.html')

@login_required
@admin_required
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
@admin_required
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
@admin_required
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

    pesquisa_respondida = PesquisaSatisfacao.objects.filter(
        aluno=OuterRef('pk')
    )

    # A query principal anota (adiciona) as informações das subqueries a cada aluno.
    alunos = Aluno.objects.annotate(
        plano_contrato=Subquery(contrato_ativo_plano),
        valor_mensalidade_contrato=Subquery(contrato_ativo_valor),
        data_ultimo_pagamento=Subquery(ultimo_pagamento),
        tem_feedback=Exists(pesquisa_respondida)
    ).order_by('nome_completo')

    context = {
        'alunos': alunos,
    }
    return render(request, 'cadastros/lista_alunos.html', context)

@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def editar_contrato(request, contrato_pk):
    """
    View para editar um contrato existente.
    """
    contrato = get_object_or_404(Contrato, pk=contrato_pk)
    aluno_pk = contrato.aluno.pk # Guarda o PK do aluno para redirecionar

    if request.method == 'POST':
        form = ContratoForm(request.POST, instance=contrato)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contrato atualizado com sucesso!')
            # Redireciona de volta para o perfil do aluno
            return redirect('cadastros:perfil_aluno', pk=aluno_pk)
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        form = ContratoForm(instance=contrato)

    context = {
        'form': form,
        'contrato': contrato, # Passa o contrato para o template
        'aluno': contrato.aluno
    }
    # Reutiliza o template de criação, que agora também servirá para edição
    return render(request, 'cadastros/criar_contrato.html', context)

@login_required
@professor_required
def editar_registro_aula(request, pk):
    registro_aula = get_object_or_404(RegistroAula, pk=pk)
    turma = registro_aula.turma # Precisamos da turma para buscar os alunos

    if request.method == 'POST':
        form = RegistroAulaForm(request.POST, instance=registro_aula)
        if form.is_valid():
            # 1. Salva os detalhes da lição (last_word, etc.)
            form.save()
            
            # =====================================================
            # ▼▼▼ LÓGICA ADICIONADA (TAREFA 2) ▼▼▼
            # =====================================================
            
            # 2. Recria os registros de presença
            alunos_presentes_ids = request.POST.getlist('presenca')
            todos_os_inscritos = Inscricao.objects.filter(
                turma=turma, 
                status__in=['matriculado', 'experimental', 'acompanhando']
            )
            
            # 3. Apaga presenças antigas e recria
            Presenca.objects.filter(registro_aula=registro_aula).delete() 
            
            for inscricao in todos_os_inscritos:
                Presenca.objects.create(
                    registro_aula=registro_aula, 
                    aluno=inscricao.aluno,
                    presente=(str(inscricao.aluno.pk) in alunos_presentes_ids)
                )
            # =====================================================
            # ▲▲▲ FIM DA LÓGICA DE PRESENÇA ▲▲▲
            # =====================================================

            messages.success(request, 'Registro de aula e presenças atualizados com sucesso!')
            return redirect('cadastros:detalhe_turma', pk=turma.pk)
    else:
        # Lógica GET
        form = RegistroAulaForm(instance=registro_aula)
        
        # =====================================================
        # ▼▼▼ LÓGICA ADICIONADA (TAREFA 2) ▼▼▼
        # =====================================================
        
        # Busca todos os alunos que deveriam estar na lista de chamada
        inscritos_turma = Inscricao.objects.filter(
            turma=turma, 
            status__in=['matriculado', 'experimental', 'acompanhando']
        ).select_related('aluno')
        
        # Busca os IDs dos alunos que foram marcados como PRESENTES
        presentes_ids = set(Presenca.objects.filter(
            registro_aula=registro_aula, 
            presente=True
        ).values_list('aluno_id', flat=True))
        # =====================================================
        # ▲▲▲ FIM DA LÓGICA DE PRESENÇA ▲▲▲
        # =====================================================

    context = {
        'form': form,
        'registro_aula': registro_aula,
        # =====================================================
        # ▼▼▼ CONTEXTO ADICIONADO (TAREFA 2) ▼▼▼
        # =====================================================
        'inscritos_turma': inscritos_turma,
        'presentes_ids': presentes_ids,
        # =====================================================
        # ▲▲▲ FIM DO CONTEXTO ▲▲▲
        # =====================================================
    }
    return render(request, 'cadastros/editar_registro_aula.html', context)

@login_required
@admin_required
def lista_leads(request):
    # A ordem das colunas no Kanban será definida por esta lista
    ordem_status = [
        'novo',
        'contatado', 
        'interessado',
        'teste_nivel',
        'negociacao',
        'agendado', 
        'congelado', 
        'convertido', 
        'perdido'
        ]

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
@admin_required
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
@admin_required
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
@admin_required
def converter_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    
    # Prepara os dados do lead para passar via URL
    # O redirect vai para o formulário de novo aluno experimental,
    # já com os campos preenchidos e com o ID do lead para referência.
    url_destino = reverse('cadastros:novo_aluno_experimental')
    parametros = f'?lead_id={lead.pk}&nome_completo={lead.nome_completo}&email={lead.email or ""}&telefone={lead.telefone or ""}'
    
    return redirect(url_destino + parametros)

@login_required
@admin_required
def gerar_link_atualizacao(request, aluno_pk):
    """
    View para o administrador gerar um link de atualização para um aluno.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    
    # Cria um novo token no banco de dados associado ao aluno
    token_obj = TokenAtualizacaoAluno.objects.create(aluno=aluno)
    
    # Constrói a URL completa que será enviada ao aluno
    link_atualizacao = request.build_absolute_uri(
        reverse('cadastros:responder_pesquisa_satisfacao', args=[token_obj.token])
    )
    
    # Adiciona uma mensagem de sucesso com o link para o admin copiar
    messages.success(
        request, 
        f"Link da PESQUISA gerado para {aluno.nome_completo}. "
        f"Envie: {link_atualizacao}"
    )
    
    # Redireciona de volta para o perfil do aluno
    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

@login_required
@admin_required
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
@professor_required
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
@professor_required
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
@professor_required
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
@professor_required
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
@aluno_required
def portal_aluno(request):
    """
    Página principal (dashboard) do Portal do Aluno.
    """
    try:
        aluno = request.user.perfil_aluno
    except Aluno.DoesNotExist:
        messages.error(request, "Acesso negado. Esta área é exclusiva para alunos.")
        return redirect('cadastros:dashboard_admin')
    
    ultimo_acompanhamento = AcompanhamentoPedagogico.objects.filter(
        aluno=aluno, status='realizado'
    ).order_by('-data_realizacao').first()

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
    
    provas_pendentes = provas_aluno.filter(status__in=['nao_iniciada', 'em_progresso'])
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
        'ultimo_acompanhamento': ultimo_acompanhamento,
        'nav': { # <-- Nova variável para a navegação
            'mes_anterior': mes_anterior, 'ano_anterior': ano_anterior,
            'mes_seguinte': mes_seguinte, 'ano_seguinte': ano_seguinte,
        }
    }
    return render(request, 'cadastros/portal_aluno.html', context)

@login_required
@aluno_required
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

@login_required
@admin_required
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
@aluno_required
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
    # 1. Busca os objetos básicos
    aluno_prova = get_object_or_404(AlunoProva, pk=aluno_prova_pk, aluno__usuario=request.user)
    prova_template = aluno_prova.prova_template
    ordem_sessoes = prova_template.ordem_sessoes
    
    # Validação de segurança: se tentar acessar uma seção que não existe
    if secao_num > len(ordem_sessoes):
        # Só redireciona para a conclusão se a prova já tiver passado da fase de execução
        if aluno_prova.status != 'finalizada':
            aluno_prova.status = 'aguardando_correcao'
            aluno_prova.save()
        return redirect('cadastros:prova_concluida', aluno_prova_pk=aluno_prova.pk)

    # 2. Configura a seção atual
    tipo_secao_atual = ordem_sessoes[secao_num - 1]
    instrucao_da_secao = prova_template.instrucoes_sessoes.get(tipo_secao_atual, "")

    questoes_da_secao = Questao.objects.filter(
        prova_template=prova_template, tipo_questao=tipo_secao_atual
    ).order_by('ordem')

    # 3. Prepara o formulário com respostas anteriores
    respostas_qs = RespostaAluno.objects.filter(
        aluno_prova=aluno_prova, questao__in=questoes_da_secao
    )
    respostas_anteriores = {resposta.questao_id: resposta for resposta in respostas_qs}

    form_fields = {}
    for questao in questoes_da_secao:
        field_name = f'questao_{questao.pk}'
        initial_value = ''
        resposta_obj = respostas_anteriores.get(questao.pk)

        # Configura widgets (Textarea ou Radio)
        if questao.tipo_questao in ['dictation', 'error_correction', 'gap_fill', 'dissertativa']:
            if resposta_obj: initial_value = resposta_obj.resposta_texto
            widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
            form_fields[field_name] = forms.CharField(label=f"Q{questao.ordem}: {questao.enunciado}", required=False, widget=widget, initial=initial_value)
        
        elif questao.tipo_questao in ['yes_no', 'multiple_choice', 'oral_multiple_choice']:
            if resposta_obj: initial_value = resposta_obj.resposta_opcao
            opcoes = list(questao.dados_questao.get('opcoes', {}).items()) if questao.tipo_questao != 'yes_no' else [('yes', 'Yes'), ('no', 'No')]
            form_fields[field_name] = forms.ChoiceField(label=f"Q{questao.ordem}: {questao.enunciado}", choices=opcoes, widget=forms.RadioSelect, required=False, initial=initial_value)
    
    ProvaSecaoForm = type('ProvaSecaoForm', (forms.Form,), form_fields)
    
    # 4. Processamento do POST
    if request.method == 'POST':
        form = ProvaSecaoForm(request.POST)
        if form.is_valid():
            # A. Salva os dados (SEMPRE, independente do botão)
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
            
            # B. Decide a navegação com base no botão clicado (name="acao")
            acao = request.POST.get('acao') 

            if acao == 'anterior':
                # Volta para a seção anterior (mínimo 1)
                nova_secao = max(1, secao_num - 1)
                return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=nova_secao)
            
            elif acao == 'sair':
                # Salva e volta para o dashboard
                messages.success(request, "Progresso salvo. Você pode continuar depois.")
                return redirect('cadastros:portal_aluno')

            elif acao == 'finalizar':
                # Finaliza a prova (somente se clicar explicitamente no botão Finalizar)
                if aluno_prova.status != 'finalizada':
                    aluno_prova.status = 'aguardando_correcao'
                    aluno_prova.save()
                return redirect('cadastros:prova_concluida', aluno_prova_pk=aluno_prova.pk)
            
            elif acao == 'proxima':
                # Avança para a próxima seção
                return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=secao_num + 1)
            
            else:
                # 🛑 SAFETY NET: Se a ação for desconhecida, MANTÉM na página atual
                return redirect('cadastros:realizar_prova_secao', aluno_prova_pk=aluno_prova.pk, secao_num=secao_num)

    else:
        form = ProvaSecaoForm()

    context = {
        'aluno_prova': aluno_prova,
        'form': form,
        'secao_atual_num': secao_num,
        'secao_atual_titulo': dict(Questao.TIPO_QUESTAO_CHOICES).get(tipo_secao_atual),
        'instrucao_da_secao': instrucao_da_secao,
        'total_secoes': len(ordem_sessoes),
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
@professor_required
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
@professor_required
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

            
            resposta_corrigida = request.POST.get(f'resposta_corrigida_{questao.id}')
            resposta.pontos_obtidos = pontos
            resposta.feedback_professor = feedback
            resposta.corrigido = True

            if resposta_corrigida:
                    resposta.resposta_corrigida_html = resposta_corrigida

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
            
            # --- LÓGICA ADICIONADA (TAREFA 1) ---
            resposta_obj = respostas_map.get(questao.id)
            texto_da_opcao = None
            if (resposta_obj and 
                resposta_obj.resposta_opcao and 
                questao.tipo_questao in ['multiple_choice', 'oral_multiple_choice', 'yes_no']):
                
                # Busca o dicionário de opções corretas (baseado na view realizar_prova_secao)
                opcoes_list = list(questao.dados_questao.get('opcoes', {}).items()) if questao.tipo_questao != 'yes_no' else [('yes', 'Yes'), ('no', 'No')]
                opcoes_dict = dict(opcoes_list)
                
                # Encontra o texto
                texto_da_opcao = opcoes_dict.get(resposta_obj.resposta_opcao, resposta_obj.resposta_opcao)
            # --- FIM DA LÓGICA ADICIONADA ---

            dados_da_secao['questoes'].append({
                'questao': questao,
                'resposta': resposta_obj,
                'texto_da_opcao': texto_da_opcao # <-- Enviando para o template
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
            
            # --- LÓGICA ADICIONADA (TAREFA 1) ---
            resposta_obj = respostas_map.get(questao.id)
            texto_da_opcao = None
            if (resposta_obj and 
                resposta_obj.resposta_opcao and 
                questao.tipo_questao in ['multiple_choice', 'oral_multiple_choice', 'yes_no']):
                
                opcoes_list = list(questao.dados_questao.get('opcoes', {}).items()) if questao.tipo_questao != 'yes_no' else [('yes', 'Yes'), ('no', 'No')]
                opcoes_dict = dict(opcoes_list)
                texto_da_opcao = opcoes_dict.get(resposta_obj.resposta_opcao, resposta_obj.resposta_opcao)
            # --- FIM DA LÓGICA ADICIONADA ---

            dados_da_secao['questoes'].append({
                'questao': questao,
                'resposta': resposta_obj,
                'texto_da_opcao': texto_da_opcao # <-- Enviando para o template
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

@login_required
@require_POST # Garante que esta view só aceite requisições POST
def marcar_experimental_desistiu(request, inscricao_pk):
    """
    Muda o status de uma inscrição experimental para 'desistiu'.
    """
    inscricao = get_object_or_404(Inscricao, pk=inscricao_pk, status='experimental')
    
    # Atualiza o status
    inscricao.status = 'desistiu'
    inscricao.save()
    
    # Também é uma boa prática de UX inativar o Aluno, se ele não tiver outras matrículas
    outras_inscricoes_ativas = Inscricao.objects.filter(
        aluno=inscricao.aluno,
        status__in=['matriculado', 'acompanhando']
    ).exclude(pk=inscricao.pk).exists()

    if not outras_inscricoes_ativas:
        inscricao.aluno.status = 'inativo' # Define o Aluno como 'inativo'
        inscricao.aluno.save()
        messages.success(request, f'Aluno "{inscricao.aluno.nome_completo}" marcado como desistente e inativado.')
    else:
        messages.success(request, f'Inscrição experimental de "{inscricao.aluno.nome_completo}" marcada como desistente.')

    return redirect('cadastros:dashboard_admin')

@login_required
@require_POST
def atualizar_status_lead(request):
    """
    View para atualizar o status de um lead via AJAX (Drag-and-Drop).
    """
    try:
        data = json.loads(request.body)
        lead_pk = data.get('lead_pk')
        novo_status = data.get('novo_status')

        # Validação
        status_validos = [choice[0] for choice in Lead.STATUS_CHOICES]
        if novo_status not in status_validos:
            return JsonResponse({'status': 'erro', 'mensagem': 'Status inválido'}, status=400)
            
        lead = get_object_or_404(Lead, pk=lead_pk)
        
        # Atualiza apenas se o status for diferente
        if lead.status != novo_status:
            lead.status = novo_status
            lead.save()
            
        return JsonResponse({'status': 'sucesso', 'lead': lead.nome_completo, 'novo_status': lead.get_status_display()})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'erro', 'mensagem': 'Request mal formatado'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

# --- VIEWS DE EXPORTAÇÃO ---

@login_required
@admin_required
def exportar_dados_page(request):
    """ Exibe a página com os botões para exportar dados. """
    return render(request, 'cadastros/exportar_dados.html')

@login_required
@admin_required
def exportar_contratos_csv(request):
    """ Gera e baixa um CSV com todos os contratos. """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mms_contratos.csv"'
    writer = csv.writer(response)

    writer.writerow([
        'ID Contrato', 'ID Aluno', 'Nome Aluno', 'Plano', 'Data Início', 'Data Fim',
        'Valor Mensalidade', 'Valor Matrícula', 'Parcelas Matrícula', 'Ativo', 'Observações'
    ])
    response.write('\ufeff'.encode('utf-8')) # Adiciona o BOM do UTF-8

    contratos = Contrato.objects.select_related('aluno').all()
    for c in contratos:
        writer.writerow([
            c.id, c.aluno.id, smart_str(c.aluno.nome_completo), c.get_plano_display(),
            c.data_inicio.strftime('%Y-%m-%d') if c.data_inicio else '',
            c.data_fim.strftime('%Y-%m-%d') if c.data_fim else '',
            f"{c.valor_mensalidade:.2f}", f"{c.valor_matricula:.2f}", c.parcelas_matricula,
            'Sim' if c.ativo else 'Não', smart_str(c.observacoes)
        ])

    response['charset'] = 'utf-8' # Garante que o charset está na resposta final
    return response

@login_required
@admin_required
def exportar_pagamentos_csv(request):
    """ Gera e baixa um CSV com todos os pagamentos. """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mms_pagamentos.csv"'
    writer = csv.writer(response)

    writer.writerow([
        'ID Pagamento', 'ID Aluno', 'Nome Aluno', 'ID Contrato', 'Tipo', 'Descrição',
        'Valor Total', 'Valor Pago', 'Status', 'Mês Referência', 'Data Vencimento', 'Data Pagamento'
    ])
    response.write('\ufeff'.encode('utf-8')) # Adiciona o BOM do UTF-8

    pagamentos = Pagamento.objects.select_related('aluno', 'contrato').all()
    for p in pagamentos:
        writer.writerow([
            p.id, p.aluno.id, smart_str(p.aluno.nome_completo), p.contrato.id if p.contrato else '',
            p.get_tipo_display(), smart_str(p.descricao), f"{p.valor:.2f}", f"{p.valor_pago:.2f}",
            p.get_status_display(), p.mes_referencia.strftime('%Y-%m-%d') if p.mes_referencia else '',
            p.data_vencimento.strftime('%Y-%m-%d') if p.data_vencimento else '',
            p.data_pagamento.strftime('%Y-%m-%d') if p.data_pagamento else ''
        ])
    response['charset'] = 'utf-8' # Garante que o charset está na resposta final
    return response

@login_required
@admin_required
def exportar_registros_aula_csv(request):
    """ Gera e baixa um CSV com todos os registros de aula. """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mms_registros_aula.csv"'
    writer = csv.writer(response)
    response.write('\ufeff'.encode('utf-8')) # Adiciona o BOM do UTF-8

    writer.writerow([
        'ID Registro', 'ID Turma', 'Nome Turma', 'Data Aula', 'ID Professor', 'Nome Professor',
        'Último Parágrafo', 'Última Palavra', 'Ditado Novo', 'Ditado Antigo',
        'Leitura Nova', 'Leitura Antiga', 'Lesson Check'
    ])

    registros = RegistroAula.objects.select_related('turma', 'professor').all()
    for r in registros:
        writer.writerow([
            r.id, r.turma.id, smart_str(r.turma.nome), r.data_aula.strftime('%Y-%m-%d') if r.data_aula else '',
            r.professor.id if r.professor else '', smart_str(r.professor.nome_completo) if r.professor else '',
            r.last_parag, smart_str(r.last_word), r.new_dictation, r.old_dictation,
            r.new_reading, r.old_reading, smart_str(r.lesson_check)
        ])
    response['charset'] = 'utf-8' # Garante que o charset está na resposta final
    return response

@login_required
@admin_required
def exportar_registros_aula_por_turma_zip(request):
    """
    Gera um arquivo ZIP contendo um CSV para cada turma com seus registros de aula.
    """
    # Cria um buffer de bytes em memória para o arquivo ZIP
    zip_buffer = io.BytesIO()

    # Cria o arquivo ZIP em memória
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        turmas = Turma.objects.all().order_by('nome')

        for turma in turmas:
            registros = RegistroAula.objects.filter(turma=turma).select_related('professor').order_by('data_aula')
            
            if not registros.exists():
                continue # Pula turmas sem registros

            # Cria um buffer de texto em memória para o CSV da turma
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)

            # Escreve o BOM e o cabeçalho
            csv_buffer.write('\ufeff') # BOM para UTF-8
            writer.writerow([
                'ID Registro', 'Data Aula', 'ID Professor', 'Nome Professor',
                'Último Parágrafo', 'Última Palavra', 'Ditado Novo', 'Ditado Antigo',
                'Leitura Nova', 'Leitura Antiga', 'Lesson Check'
            ])

            # Escreve os dados
            for r in registros:
                writer.writerow([
                    r.id, r.data_aula.strftime('%Y-%m-%d') if r.data_aula else '',
                    r.professor.id if r.professor else '', smart_str(r.professor.nome_completo) if r.professor else '',
                    r.last_parag, smart_str(r.last_word), r.new_dictation, r.old_dictation,
                    r.new_reading, r.old_reading, smart_str(r.lesson_check)
                ])
            
            # Prepara o nome do arquivo CSV dentro do ZIP
            # Remove caracteres inválidos para nomes de arquivo
            nome_turma_seguro = re.sub(r'[^\w\-]+', '_', turma.nome)
            csv_filename = f'registros_turma_{nome_turma_seguro}.csv'
            
            # Adiciona o conteúdo do CSV (como bytes UTF-8) ao ZIP
            zip_file.writestr(csv_filename, csv_buffer.getvalue().encode('utf-8'))

    # Prepara a resposta HTTP para o ZIP
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="mms_registros_aula_por_turma.zip"'
    return response

@login_required
@admin_required # Apenas administradores podem exportar dados pedagógicos
def exportar_acompanhamentos_csv(request):
    """ Gera e baixa um CSV com todos os acompanhamentos pedagógicos. """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mms_acompanhamentos_pedagogicos.csv"'
    response.write('\ufeff'.encode('utf-8')) # Adiciona o BOM do UTF-8
    writer = csv.writer(response)

    # Define os cabeçalhos
    writer.writerow([
        'ID Acompanhamento', 'ID Aluno', 'Nome Aluno', 'Status', 'Data Agendamento', 
        'Data Realização', 'Stage no Momento', 'Criado por (Professor)', 
        'Dificuldades', 'Relação Língua', 'Objetivo Estudo', 'Correção Ditados', 
        'Pontos Fortes', 'Pontos a Melhorar', 'Estratégia', 'Comentários Extras', 
        'Atividades Recomendadas'
    ])

    # Busca os dados
    acompanhamentos = AcompanhamentoPedagogico.objects.select_related('aluno', 'criado_por').all().order_by('-data_agendamento')

    for a in acompanhamentos:
        writer.writerow([
            a.id,
            a.aluno.id,
            smart_str(a.aluno.nome_completo),
            a.get_status_display(),
            a.data_agendamento.strftime('%Y-%m-%d %H:%M') if a.data_agendamento else '',
            a.data_realizacao.strftime('%Y-%m-%d %H:%M') if a.data_realizacao else '',
            a.stage_no_momento,
            smart_str(a.criado_por.nome_completo) if a.criado_por else 'N/A',
            smart_str(a.dificuldades),
            smart_str(a.relacao_lingua),
            smart_str(a.objetivo_estudo),
            smart_str(a.correcao_ditados),
            smart_str(a.pontos_fortes),
            smart_str(a.pontos_melhorar),
            smart_str(a.estrategia),
            smart_str(a.comentarios_extras),
            smart_str(a.atividades_recomendadas),
        ])
    
    response['charset'] = 'utf-8'
    return response

@login_required
@professor_required
@require_POST # Garante que esta view só aceite requisições POST
def excluir_registro_aula(request, pk):
    """
    Exclui um registro de aula e todas as suas presenças associadas.
    """
    registro_aula = get_object_or_404(RegistroAula, pk=pk)
    turma_pk = registro_aula.turma.pk # Guarda o ID da turma para o redirecionamento
    
    try:
        data_aula_formatada = registro_aula.data_aula.strftime('%d/%m/%Y')
        registro_aula.delete()
        messages.success(request, f'O registro da aula do dia {data_aula_formatada} foi excluído com sucesso.')
    except Exception as e:
        messages.error(request, f'Ocorreu um erro ao excluir o registro: {e}')
        
    # Redireciona de volta para a página de detalhes da turma
    return redirect('cadastros:detalhe_turma', pk=turma_pk)

def responder_pesquisa_satisfacao(request, token):
    # 1. Validação do Token
    try:
        token_obj = TokenAtualizacaoAluno.objects.get(token=token, usado=False)
        if token_obj.is_expired:
            return render(request, 'cadastros/token_invalido.html', {'motivo': 'O link expirou (24h). Peça um novo na secretaria.'})
    except TokenAtualizacaoAluno.DoesNotExist:
        return render(request, 'cadastros/token_invalido.html', {'motivo': 'Link inválido ou já utilizado.'})

    aluno = token_obj.aluno

    teachers = Professor.objects.filter(ativo=True, eh_teacher=True)
    equipe_adm = Professor.objects.filter(ativo=True, eh_administrativo=True)
    equipe_pedagogica = Professor.objects.filter(ativo=True, eh_pedagogico=True)

    if request.method == 'POST':
        # O formulário geral (Persona) também deve ser não-obrigatório nos campos que o model permitir
        form_geral = PesquisaSatisfacaoForm(request.POST)
        
        # Ignoramos a validação estrita do form_geral se quisermos permitir salvar mesmo incompleto,
        # mas mantemos o is_valid() para sanitização básica. Se falhar em campos obrigatórios do model, ele avisa.
        if form_geral.is_valid():
            
            # --- REMOVIDA A VALIDAÇÃO MANUAL ---
            # Agora aceitamos submissões parciais.

            with transaction.atomic():
                # A. Salva a pesquisa principal
                pesquisa = form_geral.save(commit=False)
                pesquisa.aluno = aluno
                pesquisa.save()
                
                # B. Atualiza dados do aluno (se fornecidos)
                if pesquisa.email_confirmado:
                    aluno.email = pesquisa.email_confirmado
                    if aluno.usuario:
                        aluno.usuario.email = pesquisa.email_confirmado
                        aluno.usuario.save()

                if pesquisa.telefone_atualizado:
                    aluno.telefone = pesquisa.telefone_atualizado
                aluno.save()

                # Função auxiliar para tratar vazio -> None
                def get_val(key):
                    val = request.POST.get(key)
                    return val if val else None

                # C. Salva Teachers (Aceitando Nulos)
                for teacher in teachers:
                    # Só cria o registro se pelo menos UM campo foi preenchido
                    # OU cria sempre vazio (optei por criar sempre para manter histórico de "não respondeu")
                    AvaliacaoProfessor.objects.create(
                        pesquisa=pesquisa,
                        professor=teacher,
                        satisfacao_aulas=get_val(f'teacher_{teacher.id}_satisfacao'),
                        incentivo_teacher=get_val(f'teacher_{teacher.id}_incentivo'),
                        seguranca_conforto=get_val(f'teacher_{teacher.id}_conforto'),
                        esforco_conteudo=get_val(f'teacher_{teacher.id}_esforco'),
                        elogio=request.POST.get(f'teacher_{teacher.id}_elogio', ''),
                        sugestao=request.POST.get(f'teacher_{teacher.id}_sugestao', '')
                    )

                # D. Salva Admin (Aceitando Nulos)
                for adm in equipe_adm:
                    destaques = request.POST.getlist(f'adm_{adm.id}_destaques')
                    AvaliacaoAdministrativo.objects.create(
                        pesquisa=pesquisa,
                        membro_equipe=adm,
                        educacao_prestatividade=get_val(f'adm_{adm.id}_educacao'),
                        avaliacao_geral=get_val(f'adm_{adm.id}_geral'),
                        nivel_satisfacao=get_val(f'adm_{adm.id}_satisfacao'),
                        destaques=destaques,
                        elogio=request.POST.get(f'adm_{adm.id}_elogio', ''),
                        sugestao=request.POST.get(f'adm_{adm.id}_sugestao', '')
                    )
                
                # E. Salva Pedagógico (Aceitando Nulos)
                for ped in equipe_pedagogica:
                    participou = request.POST.get(f'ped_{ped.id}_participou') == 'sim'
                    AvaliacaoPedagogico.objects.create(
                        pesquisa=pesquisa,
                        coordenador=ped,
                        participou_acompanhamento=participou,
                        satisfacao_atendimento=get_val(f'ped_{ped.id}_satisfacao') if participou else None,
                        atividades_interessantes=request.POST.get(f'ped_{ped.id}_atividades', ''),
                        elogio=request.POST.get(f'ped_{ped.id}_elogio', ''),
                        sugestao=request.POST.get(f'ped_{ped.id}_sugestao', '')
                    )

                token_obj.usado = True
                token_obj.save()

            return render(request, 'cadastros/feedback_sucesso.html')
        else:
            # Se o form_geral falhar (ex: campo email inválido), mostra erro
            messages.error(request, "Verifique os dados de contato.")
    else:
        initial_data = {
            'email_confirmado': aluno.email,
            'telefone_atualizado': aluno.telefone,
            'stage_atual_informado': aluno.inscricao_set.first().turma.stage if aluno.inscricao_set.exists() else 1
        }
        form_geral = PesquisaSatisfacaoForm(initial=initial_data)

    context = {
        'aluno': aluno,
        'form_geral': form_geral,
        'teachers': teachers,
        'equipe_adm': equipe_adm,
        'equipe_pedagogica': equipe_pedagogica,
    }
    return render(request, 'cadastros/responder_feedback.html', context)

# --- VIEWS PARA "ESQUECI MINHA SENHA" (Preparação Sprint 2) ---

def esqueci_minha_senha(request):
    """
    Solicita o e-mail para envio de recuperação.
    Funciona tanto para Alunos quanto para Professores (pois ambos têm User).
    """
    if request.method == 'POST':
        form = EsqueciSenhaForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                # Procura usuários com esse e-mail
                users = User.objects.filter(email=email)
                if users.exists():
                    for user in users:
                        # Aqui usaremos a função nativa do Django de reset password
                        # Mas personalizaremos o template de email depois
                        form_reset = auth_views.PasswordResetForm({'email': email})
                        if form_reset.is_valid():
                            # --- BLOCO CORRIGIDO ---
                            form_reset.save(
                                request=request,
                                use_https=request.is_secure(),
                                # 1. Versão Texto Puro (Anti-Spam)
                                email_template_name='cadastros/emails/password_reset_email.txt',
                                # 2. Versão HTML (Visual) - É AQUI QUE A MÁGICA ACONTECE
                                html_email_template_name='cadastros/emails/password_reset_email.html',
                                subject_template_name='cadastros/emails/password_reset_subject.txt'
                            )
                            # -----------------------
                    messages.success(request, 'Se o e-mail estiver cadastrado, você receberá um link de redefinição. Olhe os SPAM também!')
                    return redirect('cadastros:portal_login')
                else:
                    # Por segurança, não dizemos que o email não existe, apenas dizemos que enviamos
                    messages.success(request, 'Se o e-mail estiver cadastrado, você receberá um link de redefinição.')
            except Exception as e:
                messages.error(request, 'Erro ao processar solicitação.')
    else:
        form = EsqueciSenhaForm()
    
    return render(request, 'cadastros/esqueci_senha.html', {'form': form})

@login_required
@admin_required
def cancelar_contrato(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    
    if request.method == 'POST':
        hoje = timezone.now().date()
        
        # 1. Calcula meses restantes baseados na DATA FIM do contrato
        # (Ex: Hoje é Jan, Fim é Dez -> 11 meses restantes)
        r = relativedelta(contrato.data_fim, hoje)
        meses_restantes = r.years * 12 + r.months
        
        if meses_restantes < 0: meses_restantes = 0
        
        # 2. Multa: 50% do valor das mensalidades restantes
        valor_total_restante = meses_restantes * contrato.valor_mensalidade
        multa = valor_total_restante * Decimal('0.5')
        
        # 3. Gera a cobrança da multa (Vencimento Hoje)
        if multa > 0:
            Pagamento.objects.create(
                aluno=contrato.aluno,
                contrato=contrato,
                tipo='outro',
                descricao=f"Multa Rescisória - Cancelamento ({meses_restantes} meses restantes)",
                valor=multa,
                mes_referencia=hoje,
                data_vencimento=hoje,
                status='pendente'
            )
        
        # 4. Encerra o contrato e cancela cobranças futuras
        contrato.status = 'cancelado'
        contrato.ativo = False
        contrato.save()
        
        # Cancela boletos futuros que ainda não foram pagos
        Pagamento.objects.filter(
            contrato=contrato,
            status='pendente',
            data_vencimento__gt=hoje
        ).update(status='cancelado')

        messages.warning(request, f'Contrato CANCELADO. Multa de R$ {multa:.2f} gerada.')
        return redirect('cadastros:perfil_aluno', pk=contrato.aluno.pk)

    return render(request, 'cadastros/confirmar_cancelamento.html', {'contrato': contrato, 'hoje': timezone.now().date()})

# --- LÓGICA DE TRANCAMENTO ---
@login_required
@admin_required
def trancar_contrato(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    
    # 1. Tranca o contrato
    contrato.status = 'trancado'
    contrato.save()
    
    # 2. Tranca o Aluno (Atualiza status global)
    aluno = contrato.aluno
    aluno.status = 'trancado'
    aluno.save()
    
    # 3. Atualiza inscrições ativas para 'trancado'
    Inscricao.objects.filter(aluno=aluno, status__in=['matriculado', 'acompanhando']).update(status='trancado')
    
    messages.warning(request, f'Contrato e Matrícula de {aluno.nome_completo} foram TRANCADOS. Cobranças futuras gerarão créditos.')
    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

# --- LÓGICA DE QUITAR (Gerar Crédito se Trancado) ---
# ATENÇÃO: Substitua a sua view 'quitar_pagamento_especifico' atual por esta
@login_required
@admin_required
def quitar_pagamento_especifico(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    contrato = pagamento.contrato
    aluno = pagamento.aluno

    # 1. Marca como Pago
    pagamento.status = 'pago'
    pagamento.valor_pago = pagamento.valor
    pagamento.data_pagamento = timezone.now().date()
    pagamento.save()

    # 2. Regra do Trancamento (Acúmulo de Crédito)
    # Se o contrato está trancado e é uma mensalidade, o aluno ganha +1 crédito
    if contrato and contrato.status == 'trancado' and pagamento.tipo == 'mensalidade':
        aluno.creditos_aulas += 1
        aluno.save()
        messages.success(request, f"Pagamento confirmado! O aluno ganhou +1 CRÉDITO DE AULA (Total: {aluno.creditos_aulas}).")
    else:
        messages.success(request, "Pagamento quitado com sucesso.")

    # Retorna para a página anterior (Dashboard ou Perfil)
    return redirect(request.META.get('HTTP_REFERER', 'cadastros:dashboard_admin'))

# --- LÓGICA DE USO DE CRÉDITO (Para o Cenário A e B) ---
@login_required
@admin_required
def usar_credito_pagamento(request, pk):
    """
    Usa 1 crédito do aluno para quitar uma mensalidade pendente.
    """
    pagamento = get_object_or_404(Pagamento, pk=pk)
    aluno = pagamento.aluno
    
    if aluno.creditos_aulas > 0:
        # Abate 1 crédito
        aluno.creditos_aulas -= 1
        aluno.save()
        
        # Quita a cobrança
        pagamento.status = 'pago'
        pagamento.valor_pago = 0 # Valor financeiro pago é 0, pois foi crédito
        pagamento.data_pagamento = timezone.now().date()
        pagamento.descricao += " (PAGO COM CRÉDITO)"
        pagamento.save()
        
        messages.success(request, f"Mensalidade quitada usando 1 Crédito! Restam: {aluno.creditos_aulas}")
    else:
        messages.error(request, "O aluno não possui créditos disponíveis.")
        
    return redirect('cadastros:perfil_aluno', pk=aluno.pk)

# 2. NOVAS VIEWS DE GESTÃO DE TURMA (Adicione ao final do arquivo)
# ==============================================================================

@login_required
@admin_required
@require_POST
def adicionar_turma_aluno(request, aluno_pk):
    """
    Matricula o aluno numa turma diretamente pelo perfil.
    """
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    turma_id = request.POST.get('turma')
    
    if turma_id:
        turma = get_object_or_404(Turma, pk=turma_id)
        # Verifica se já não está matriculado para não duplicar
        if not Inscricao.objects.filter(aluno=aluno, turma=turma).exists():
            Inscricao.objects.create(
                aluno=aluno,
                turma=turma,
                status='matriculado' # Default
            )
            messages.success(request, f'{aluno.nome_completo} matriculado em {turma.nome}.')
        else:
            messages.warning(request, 'O aluno já pertence a esta turma.')
    
    return redirect('cadastros:perfil_aluno', pk=aluno_pk)

@login_required
@admin_required
def gerenciar_inscricao(request, inscricao_pk):
    """
    Permite Excluir ou Editar o status de uma inscrição.
    """
    inscricao = get_object_or_404(Inscricao, pk=inscricao_pk)
    aluno_pk = inscricao.aluno.pk

    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'excluir':
            turma_nome = inscricao.turma.nome
            inscricao.delete()
            messages.success(request, f'Matrícula na turma {turma_nome} removida.')
        
        elif acao == 'editar_status':
            novo_status = request.POST.get('novo_status')
            if novo_status:
                inscricao.status = novo_status
                inscricao.save()
                messages.success(request, f'Status na turma {inscricao.turma.nome} atualizado.')

    return redirect('cadastros:perfil_aluno', pk=aluno_pk)


# ==============================================================================
# 3. LÓGICA DE VERIFICAÇÃO DE FALTAS (Helper Function)
# ==============================================================================

def _verificar_e_gerar_alerta_faltas(aluno):
    """
    Função utilitária para verificar se o aluno tem 3 faltas consecutivas 
    e gerar um alerta, EVITANDO DUPLICIDADE.
    Deve ser chamada sempre que uma falta é registrada.
    """
    # 1. Verifica se JÁ EXISTE um acompanhamento pendente. Se sim, não faz nada.
    if AcompanhamentoFalta.objects.filter(aluno=aluno, status='pendente').exists():
        return # Já tem alerta aberto, não precisa spammar.

    # 2. Busca as últimas 3 presenças do aluno (ordenadas da mais recente para antiga)
    ultimas_presencas = Presenca.objects.filter(aluno=aluno).order_by('-registro_aula__data_aula')[:3]
    
    # Se tiver menos de 3 aulas registradas, não tem como ter 3 faltas seguidas
    if len(ultimas_presencas) < 3:
        return

    # 3. Verifica se as 3 são faltas (presente=False)
    # A lista vem [Recente, Anterior, Antepenúltima]
    faltas_consecutivas = all(p.presente is False for p in ultimas_presencas)
    
    if faltas_consecutivas:
        data_inicio = ultimas_presencas[2].registro_aula.data_aula # A data da 1ª falta da sequência
        
        AcompanhamentoFalta.objects.create(
            aluno=aluno,
            data_inicio_sequencia=data_inicio,
            numero_de_faltas=3,
            status='pendente',
            motivo="Alerta Automático: 3 faltas consecutivas detectadas."
        )

# --- ONDE CHAMAR ESSA FUNÇÃO? ---
# Você deve adicionar a chamada `_verificar_e_gerar_alerta_faltas(inscricao.aluno)`
# dentro das views 'detalhe_turma' e 'editar_registro_aula', logo após criar a Presenca=False.
# Exemplo (pseudocódigo para você inserir nas views existentes):
# if not presente:
#    _verificar_e_gerar_alerta_faltas(inscricao.aluno)

@login_required
@admin_required
@require_POST
def excluir_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    nome = lead.nome_completo
    lead.delete()
    messages.success(request, f'Lead "{nome}" removido com sucesso.')
    return redirect('cadastros:lista_leads')

@login_required
@admin_required
def destrancar_contrato(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    
    if contrato.status == 'trancado':
        # 1. Reativa contrato
        contrato.status = 'ativo'
        contrato.save()
        
        # 2. Reativa aluno
        aluno = contrato.aluno
        aluno.status = 'ativo'
        aluno.save()
        
        # 3. Reativa inscrições
        Inscricao.objects.filter(aluno=aluno, status='trancado').update(status='matriculado')
        
        messages.success(request, f'Contrato de {aluno.nome_completo} DESTRANCADO com sucesso! Status voltou para Ativo.')
    
    return redirect('cadastros:perfil_aluno', pk=contrato.aluno.pk)

@login_required
@admin_required
def dashboard_marketing(request):
    # --- 1. DADOS DE LEADS (Funil de Vendas) ---
    leads_total = Lead.objects.count()
    leads_convertidos = Lead.objects.filter(status='convertido').count()
    taxa_conversao = (leads_convertidos / leads_total * 100) if leads_total > 0 else 0
    
    # Origem dos Leads (Gráfico de Pizza)
    fontes_qs = Lead.objects.values('fonte_contato').annotate(total=Count('id')).order_by('-total')
    dict_fontes = dict(Lead.FONTE_CHOICES)
    dados_fontes = {
        'labels': [dict_fontes.get(item['fonte_contato'], item['fonte_contato']) for item in fontes_qs],
        'data': [item['total'] for item in fontes_qs]
    }

    # --- 2. DADOS DEMOGRÁFICOS (Pesquisa de Satisfação) ---
    
    # A. Faixa Etária
    faixa_etaria_qs = PesquisaSatisfacao.objects.values('faixa_etaria').annotate(total=Count('id'))
    dict_faixa = dict(PesquisaSatisfacao.FAIXA_ETARIA_CHOICES)
    dados_faixa = {
        'labels': [dict_faixa.get(item['faixa_etaria'], item['faixa_etaria']) for item in faixa_etaria_qs],
        'data': [item['total'] for item in faixa_etaria_qs]
    }

    # B. Como Conheceu
    conheceu_qs = PesquisaSatisfacao.objects.values('como_conheceu').annotate(total=Count('id'))
    dict_conheceu = dict(PesquisaSatisfacao.COMO_CONHECEU_CHOICES)
    dados_conheceu = {
        'labels': [dict_conheceu.get(item['como_conheceu'], item['como_conheceu']) for item in conheceu_qs],
        'data': [item['total'] for item in conheceu_qs]
    }

    # C. Escolaridade
    escolaridade_qs = PesquisaSatisfacao.objects.values('escolaridade').annotate(total=Count('id'))
    dict_escolaridade = dict(PesquisaSatisfacao.ESCOLARIDADE_CHOICES)
    dados_escolaridade = {
        'labels': [dict_escolaridade.get(item['escolaridade'], item['escolaridade']) for item in escolaridade_qs],
        'data': [item['total'] for item in escolaridade_qs]
    }

    # D. Área de Atuação (Top 8 - já que é texto livre)
    area_qs = PesquisaSatisfacao.objects.values('area_atuacao').annotate(total=Count('id')).order_by('-total')[:8]
    dados_area = {
        'labels': [item['area_atuacao'] or 'Não informado' for item in area_qs],
        'data': [item['total'] for item in area_qs]
    }

    # E. Objetivo com Inglês (Top 5)
    objetivo_qs = PesquisaSatisfacao.objects.values('objetivo_ingles').annotate(total=Count('id')).order_by('-total')[:5]
    dados_objetivo = {
        'labels': [item['objetivo_ingles'] or 'Não informado' for item in objetivo_qs],
        'data': [item['total'] for item in objetivo_qs]
    }

    context = {
        'leads_total': leads_total,
        'leads_convertidos': leads_convertidos,
        'taxa_conversao': round(taxa_conversao, 1),
        'dados_fontes': json.dumps(dados_fontes),
        'dados_faixa': json.dumps(dados_faixa),
        'dados_conheceu': json.dumps(dados_conheceu),
        # Novos Contextos
        'dados_escolaridade': json.dumps(dados_escolaridade),
        'dados_area': json.dumps(dados_area),
        'dados_objetivo': json.dumps(dados_objetivo),
    }
    return render(request, 'cadastros/dashboard_marketing.html', context)

@login_required
@admin_required
def dashboard_feedback(request):
    # ==========================================
    # 1. VISÃO GERAL & MARKETING
    # ==========================================
    nps_stats = PesquisaSatisfacao.objects.aggregate(
        total=Count('id'),
        promotores=Count('id', filter=Q(nps_score__gte=9)),
        detratores=Count('id', filter=Q(nps_score__lte=6)),
        neutros=Count('id', filter=Q(nps_score__range=(7, 8)))
    )
    total_respostas = nps_stats['total'] or 0
    promotores = nps_stats['promotores'] or 0
    detratores = nps_stats['detratores'] or 0
    neutros = nps_stats['neutros'] or 0
    
    nps_score = 0
    if total_respostas > 0:
        pct_promotores = promotores / total_respostas
        pct_detratores = detratores / total_respostas
        nps_score = (pct_promotores - pct_detratores) * 100

    insta_stats = PesquisaSatisfacao.objects.aggregate(
        seguem=Count('id', filter=Q(segue_instagram=True)),
        nao_seguem=Count('id', filter=Q(segue_instagram=False))
    )
    
    sugestoes_conteudo = PesquisaSatisfacao.objects.exclude(conteudo_desejado__exact='').exclude(conteudo_desejado__isnull=True).values('conteudo_desejado', 'data_resposta').order_by('-data_resposta')
    comentarios_gerais = PesquisaSatisfacao.objects.exclude(comentarios_gerais__exact='').exclude(comentarios_gerais__isnull=True).order_by('-data_resposta')

    # ==========================================
    # 2. ADMINISTRATIVO
    # ==========================================
    admins = Professor.objects.filter(eh_administrativo=True, ativo=True)
    admins_data = []
    for a in admins:
        avals = a.avaliacaoadministrativo_set.select_related('pesquisa').all().order_by('-id')
        stats = avals.aggregate(
            media_atendimento=Avg('avaliacao_geral'),
            media_satisfacao=Avg('nivel_satisfacao'),
            media_educacao=Avg('educacao_prestatividade')
        )
        todos_destaques = []
        for av in avals:
            if av.destaques and isinstance(av.destaques, list): todos_destaques.extend(av.destaques)
        contagem_destaques = Counter(todos_destaques).most_common()
        feedbacks_texto = [av for av in avals if av.elogio or av.sugestao]
        admins_data.append({'membro': a, 'stats': stats, 'destaques': contagem_destaques, 'feedbacks': feedbacks_texto, 'qtd': avals.count()})

    # ==========================================
    # 3. PROFESSORES (GERAL - ABA TEACHERS)
    # ==========================================
    teachers = Professor.objects.filter(eh_teacher=True, ativo=True)
    teachers_data = []
    
    for t in teachers:
        # Apenas dados gerais aqui. O detalhe por turma fica na Seção 5.
        avals = t.avaliacaoprofessor_set.select_related('pesquisa').all().order_by('-id')
        stats = avals.aggregate(
            media_sat=Avg('satisfacao_aulas'), 
            media_inc=Avg('incentivo_teacher'), 
            media_seg=Avg('seguranca_conforto'), 
            media_esf=Avg('esforco_conteudo')
        )
        feedbacks_texto = [a for a in avals if a.elogio or a.sugestao]
        
        teachers_data.append({
            'professor': t, 
            'stats': stats, 
            'feedbacks': feedbacks_texto, 
            'qtd': avals.count()
        })

    # ==========================================
    # 4. PEDAGÓGICO
    # ==========================================
    pedagogicos = Professor.objects.filter(eh_pedagogico=True, ativo=True)
    peds_data = []
    for p in pedagogicos:
        avals = p.avaliacaopedagogico_set.select_related('pesquisa').all().order_by('-id')
        stats = avals.aggregate(media_sat=Avg('satisfacao_atendimento'))
        feedbacks_texto = [av for av in avals if av.elogio or av.sugestao or av.atividades_interessantes]
        peds_data.append({'coordenador': p, 'stats': stats, 'feedbacks': feedbacks_texto, 'qtd': avals.count()})

    # ==========================================
    # 5. DETALHAMENTO E GRÁFICO POR TURMA
    # ==========================================
    
    # PARTE A: Dados para o Gráfico de Barras (NPS Médio por Turma)
    turma_subquery = Inscricao.objects.filter(
        aluno=OuterRef('aluno'),
        status__in=['matriculado', 'acompanhando', 'experimental']
    ).order_by('-id').values('turma__nome')[:1]

    qs_grafico = PesquisaSatisfacao.objects.annotate(
        turma_atual=Subquery(turma_subquery)
    ).values('turma_atual').annotate(
        media_nps=Avg('nps_score'),
        total_respostas=Count('id')
    ).exclude(turma_atual__isnull=True).order_by('-media_nps')

    dados_turmas = {
        'labels': [item['turma_atual'] for item in qs_grafico],
        'data': [round(item['media_nps'], 1) for item in qs_grafico]
    }

    # PARTE B: Dados para o Acordeão (Lista detalhada: Turma -> Professores)
    turmas_ativas = Turma.objects.filter(
        inscricao__status__in=['matriculado', 'acompanhando', 'experimental']
    ).distinct().order_by('nome')

    turmas_data = []

    for turma in turmas_ativas:
        # Descobre quais professores receberam avaliação nesta turma
        profs_na_turma = Professor.objects.filter(
            avaliacaoprofessor__pesquisa__aluno__inscricao__turma=turma,
            eh_teacher=True
        ).distinct()

        if not profs_na_turma.exists():
            continue

        lista_profs_turma = []
        for prof in profs_na_turma:
            # Filtra avaliações específicas deste par (Professor + Turma)
            avals_especificas = AvaliacaoProfessor.objects.filter(
                professor=prof,
                pesquisa__aluno__inscricao__turma=turma
            )

            stats_turma = avals_especificas.aggregate(
                media_sat=Avg('satisfacao_aulas'),
                media_inc=Avg('incentivo_teacher'),
                media_seg=Avg('seguranca_conforto'),
                media_esf=Avg('esforco_conteudo')
            )
            
            feedbacks_turma = [a for a in avals_especificas if a.elogio or a.sugestao]

            lista_profs_turma.append({
                'professor': prof,
                'stats': stats_turma,
                'feedbacks': feedbacks_turma,
                'qtd': avals_especificas.count()
            })

        # Ordena os professores pela maior média
        lista_profs_turma.sort(key=lambda x: x['stats']['media_sat'] or 0, reverse=True)

        turmas_data.append({
            'turma': turma,
            'professores': lista_profs_turma
        })

    context = {
        'nps_score': round(nps_score),
        'total_respostas': total_respostas,
        'distribuicao_nps': json.dumps([promotores, neutros, detratores]),
        'insta_data': json.dumps([insta_stats['seguem'], insta_stats['nao_seguem']]),
        'dados_turmas': json.dumps(dados_turmas), # Gráfico
        'turmas_data': turmas_data,               # Acordeão
        'comentarios_gerais': comentarios_gerais,
        'sugestoes_conteudo': sugestoes_conteudo,
        'teachers_data': teachers_data,
        'admins_data': admins_data,
        'peds_data': peds_data,
    }
    return render(request, 'cadastros/dashboard_feedback.html', context)

@login_required
@admin_required
def enviar_email_alunos(request):
    if request.method == 'POST':
        form = EnviarEmailForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data['tipo_destinatario']
            assunto = form.cleaned_data['assunto']
            mensagem = form.cleaned_data['mensagem']
            
            destinatarios_emails = []

            if tipo == 'todos':
                # Pega e-mails de alunos ativos
                destinatarios_emails = list(Aluno.objects.filter(status='ativo').exclude(email='').values_list('email', flat=True))
            
            elif tipo == 'turma':
                turma = form.cleaned_data['turma']
                if turma:
                    destinatarios_emails = list(Aluno.objects.filter(
                        inscricao__turma=turma, 
                        inscricao__status__in=['matriculado', 'acompanhando']
                    ).exclude(email='').values_list('email', flat=True))
            
            elif tipo == 'aluno':
                aluno = form.cleaned_data['aluno']
                if aluno and aluno.email:
                    destinatarios_emails = [aluno.email]

            # Envia os e-mails (usando BCC para privacidade se for em massa)
            if destinatarios_emails:
                try:
                    # Envia como cópia oculta (BCC) para ninguém ver o e-mail do outro
                    msg = EmailMultiAlternatives(
                        subject=f"[MMS Portal] {assunto}",
                        body=mensagem,
                        from_email=None, # Usa o DEFAULT_FROM_EMAIL do settings
                        bcc=destinatarios_emails
                    )
                    msg.send()
                    messages.success(request, f"E-mail enviado para {len(destinatarios_emails)} alunos com sucesso!")
                except Exception as e:
                    messages.error(request, f"Erro ao enviar e-mail: {e}")
            else:
                messages.warning(request, "Nenhum destinatário com e-mail válido encontrado.")
                
            return redirect('cadastros:dashboard_admin')
    else:
        form = EnviarEmailForm()

    return render(request, 'cadastros/enviar_email.html', {'form': form})