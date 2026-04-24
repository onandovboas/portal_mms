import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Aluno, HorarioDisponivelAluno

def coletar_disponibilidade_aluno(request, token):
    aluno = get_object_or_404(Aluno, token_disponibilidade=token)

    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            horarios = dados.get('horarios', [])

            # Limpar horários antigos
            aluno.horarios_disponiveis.all().delete()

            for horario in horarios:
                dia = horario.get('dia')
                inicio = horario.get('inicio')
                fim = horario.get('fim')
                if dia is not None and inicio and fim:
                    HorarioDisponivelAluno.objects.create(
                        aluno=aluno,
                        dia_semana=int(dia),
                        horario_inicio=inicio,
                        horario_fim=fim
                    )
            
            return JsonResponse({'status': 'success', 'message': 'Disponibilidade salva com sucesso!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # Configuração inicial do calendário
    dias_semana = [{'valor': k, 'nome': v} for k, v in HorarioDisponivelAluno.DIA_CHOICES]
    slots_horarios = [f"{str(h).zfill(2)}:00" for h in range(7, 23)]

    horarios_selecionados = [
        {
            'dia': hd.dia_semana,
            'inicio': hd.horario_inicio.strftime('%H:%M'),
            'fim': hd.horario_fim.strftime('%H:%M')
        } for hd in aluno.horarios_disponiveis.all()
    ]

    # Para alunos trancados, o 'stage_atual' vem da última inscrição ativa ou trancada
    inscricao = aluno.inscricao_set.filter(status__in=['matriculado', 'trancado']).select_related('turma').first()
    stage_atual = inscricao.turma.stage if inscricao else 0

    dados_config = {
        'dias_semana': dias_semana,
        'slots_horarios': slots_horarios,
        'horarios_selecionados': horarios_selecionados,
        'stage_atual': stage_atual
    }

    context = {
        'aluno': aluno,
        'dados_config': dados_config
    }
    return render(request, 'cadastros/alunos/disponibilidade_publica_aluno.html', context)
