import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from .models import Lead, HorarioDisponivelLead
from django.views.decorators.csrf import csrf_exempt

def coletar_disponibilidade_lead(request, token):
    lead = get_object_or_404(Lead, token_disponibilidade=token)

    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            horarios = dados.get('horarios', [])

            # Limpar horários antigos para evitar duplicatas ao re-submeter
            lead.horarios_disponiveis.all().delete()

            for horario in horarios:
                dia = horario.get('dia')
                inicio = horario.get('inicio')
                fim = horario.get('fim')
                if dia is not None and inicio and fim:
                    HorarioDisponivelLead.objects.create(
                        lead=lead,
                        dia_semana=int(dia),
                        horario_inicio=inicio,
                        horario_fim=fim
                    )
            
            return JsonResponse({'status': 'success', 'message': 'Disponibilidade salva com sucesso!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # Configuração inicial do calendário enviada via json_script
    dias_semana = [{'valor': k, 'nome': v} for k, v in HorarioDisponivelLead.DIA_CHOICES]
    # Gerar os slots de 1 hora das 07:00 as 22:00
    slots_horarios = [f"{str(h).zfill(2)}:00" for h in range(7, 23)]

    # Recupera horários já selecionados caso o usuário esteja reabrindo o link
    horarios_selecionados = [
        {
            'dia': hd.dia_semana,
            'inicio': hd.horario_inicio.strftime('%H:%M'),
            'fim': hd.horario_fim.strftime('%H:%M')
        } for hd in lead.horarios_disponiveis.all()
    ]

    dados_config = {
        'dias_semana': dias_semana,
        'slots_horarios': slots_horarios,
        'horarios_selecionados': horarios_selecionados,
        'stage_atual': lead.stage_interesse
    }

    context = {
        'lead': lead,
        'dados_config': dados_config
    }
    return render(request, 'cadastros/leads/disponibilidade_publica.html', context)
