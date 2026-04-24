from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Lead

@login_required
def descartar_lead(request):
    if request.method == 'POST':
        lead_pk = request.POST.get('lead_pk')
        motivo = request.POST.get('motivo_descarte')
        acao = request.POST.get('acao') # perdido ou congelado

        lead = get_object_or_404(Lead, pk=lead_pk)
        lead.status = acao
        lead.motivo_descarte = motivo
        lead.save()

        msg = f'Lead "{lead.nome_completo}" atualizado para {lead.get_status_display()} com sucesso.'
        messages.success(request, msg)

    return redirect('cadastros:lista_leads')
