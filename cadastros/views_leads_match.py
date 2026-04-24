from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Lead, HorarioDisponivelLead, Inscricao, HorarioDisponivelAluno, Aluno
from collections import defaultdict

@login_required
def dashboard_match_horarios(request):
    stage_selecionado = request.GET.get('stage', '')
    
    # Pegar todos os stages únicos que têm leads interessados ou alunos trancados
    stages_leads = set(Lead.objects.exclude(stage_interesse__isnull=True).values_list('stage_interesse', flat=True))
    stages_trancados = set(Inscricao.objects.filter(status='trancado').values_list('turma__stage', flat=True))
    stages_disponiveis = sorted(list(stages_leads | stages_trancados))
    
    match_data = {}
    dias_nomes = dict(HorarioDisponivelLead.DIA_CHOICES)
    alunos_trancados_lista = []
    
    if stage_selecionado:
        # 1. Agrupar Disponibilidade de Leads
        leads = Lead.objects.filter(stage_interesse=stage_selecionado, status__in=['novo', 'contatado', 'interessado', 'teste_nivel'])
        horarios_leads = HorarioDisponivelLead.objects.filter(lead__in=leads)
        
        agrupamento = defaultdict(lambda: defaultdict(list))
        
        for h in horarios_leads:
            inicio_str = h.horario_inicio.strftime('%H:%M')
            agrupamento[h.dia_semana][inicio_str].append({
                'tipo': 'Lead',
                'id': h.lead.pk,
                'nome': h.lead.nome_completo,
                'telefone': h.lead.telefone
            })

        # 2. Agrupar Disponibilidade de Alunos Trancados
        alunos_trancados = Aluno.objects.filter(status='trancado', inscricao__turma__stage=stage_selecionado).distinct()
        horarios_alunos = HorarioDisponivelAluno.objects.filter(aluno__in=alunos_trancados)

        for h in horarios_alunos:
            inicio_str = h.horario_inicio.strftime('%H:%M')
            agrupamento[h.dia_semana][inicio_str].append({
                'tipo': 'Aluno',
                'id': h.aluno.pk,
                'nome': h.aluno.nome_completo,
                'telefone': h.aluno.telefone
            })
            
        # Formatar para o template
        for dia_idx in range(7):
            if dia_idx in agrupamento:
                match_data[dias_nomes[dia_idx]] = dict(sorted(agrupamento[dia_idx].items()))

        # Lista de Alunos Trancados naquele Stage (para a visualização separada)
        inscricoes_trancadas = Inscricao.objects.filter(status='trancado', turma__stage=stage_selecionado).select_related('aluno', 'turma')
        for insc in inscricoes_trancadas:
            alunos_trancados_lista.append({
                'id': insc.aluno.pk,
                'nome': insc.aluno.nome_completo,
                'telefone': insc.aluno.telefone,
                'turma_original': insc.turma.nome,
                'creditos': insc.aluno.creditos_aulas
            })

    # Preparar a estrutura da tabela
    todos_horarios = set()
    for dia_dados in match_data.values():
        todos_horarios.update(dia_dados.keys())
    
    horarios_ordenados = sorted(list(todos_horarios))
    dias_colunas = [dias_nomes[i] for i in range(7) if dias_nomes[i] in match_data]

    context = {
        'stages_disponiveis': stages_disponiveis,
        'stage_selecionado': int(stage_selecionado) if stage_selecionado else '',
        'match_data': match_data,
        'horarios_ordenados': horarios_ordenados if stage_selecionado else [],
        'dias_colunas': dias_colunas if stage_selecionado else [],
        'alunos_trancados': alunos_trancados_lista,
    }
    
    return render(request, 'cadastros/leads/match_horarios.html', context)
