from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Lead, HorarioDisponivelLead
from collections import defaultdict

@login_required
def dashboard_match_horarios(request):
    stage_selecionado = request.GET.get('stage', '')
    
    # Pegar todos os stages únicos que têm leads interessados
    stages_disponiveis = Lead.objects.exclude(stage_interesse__isnull=True).values_list('stage_interesse', flat=True).distinct().order_by('stage_interesse')
    
    match_data = {}
    dias_nomes = dict(HorarioDisponivelLead.DIA_CHOICES)
    
    if stage_selecionado:
        # Pega todos os leads que estão naquele stage
        leads = Lead.objects.filter(stage_interesse=stage_selecionado, status__in=['novo', 'contatado', 'interessado', 'teste_nivel'])
        horarios = HorarioDisponivelLead.objects.filter(lead__in=leads)
        
        # Agrupar por dia e horário: match_data[dia][horario] = [lead1, lead2, ...]
        agrupamento = defaultdict(lambda: defaultdict(list))
        
        for h in horarios:
            inicio_str = h.horario_inicio.strftime('%H:%M')
            agrupamento[h.dia_semana][inicio_str].append({
                'id': h.lead.pk,
                'nome': h.lead.nome_completo,
                'telefone': h.lead.telefone
            })
            
        # Formatar para o template
        for dia_idx in range(7):
            if dia_idx in agrupamento:
                match_data[dias_nomes[dia_idx]] = dict(sorted(agrupamento[dia_idx].items()))

    # Preparar a estrutura da tabela
    # Coletar todos os horários únicos (linhas da tabela)
    todos_horarios = set()
    for dia_dados in match_data.values():
        todos_horarios.update(dia_dados.keys())
    
    horarios_ordenados = sorted(list(todos_horarios))
    dias_colunas = [dias_nomes[i] for i in range(7) if dias_nomes[i] in match_data]

    context = {
        'stages_disponiveis': stages_disponiveis,
        'stage_selecionado': stage_selecionado,
        'match_data': match_data,
        'horarios_ordenados': horarios_ordenados if stage_selecionado else [],
        'dias_colunas': dias_colunas if stage_selecionado else []
    }
    
    return render(request, 'cadastros/leads/match_horarios.html', context)
