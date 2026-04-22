import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Max

from .models import Lead, MensagemWhatsApp, TemplateMensagem
from .forms import LeadForm
from .views_webhook import enviar_mensagem_whatsapp 

@login_required
def caixa_de_entrada_chat(request, lead_pk=None):
    """ Renderiza a Caixa de Entrada Centralizada (Inbox de 3 colunas) """
    
    # 1. Coluna Esquerda: Todos os Leads (ordenados pela mensagem mais recente, e depois pelos mais novos)
    leads_com_chat = Lead.objects.annotate(
        ultima_mensagem=Max('mensagens_whatsapp__data_envio')
    ).order_by('-ultima_mensagem', '-data_criacao')

    lead_selecionado = None
    mensagens = []
    form_lead = None
    templates = TemplateMensagem.objects.all().order_by('categoria', 'titulo')

    # 2 & 3. Coluna Central (Chat) e Direita (Formulário CRM)
    if lead_pk:
        lead_selecionado = get_object_or_404(Lead, pk=lead_pk)
        mensagens = MensagemWhatsApp.objects.filter(lead=lead_selecionado).order_by('data_envio')
        
        # Lida com a gravação do formulário da coluna da direita (quando você altera o status, etc.)
        if request.method == 'POST':
            form_lead = LeadForm(request.POST, instance=lead_selecionado)
            if form_lead.is_valid():
                form_lead.save()
                messages.success(request, f'Dados de {lead_selecionado.nome_completo} atualizados com sucesso!')
                return redirect('cadastros:caixa_de_entrada_chat_lead', lead_pk=lead_selecionado.pk)
        else:
            # Carrega o formulário pré-preenchido com os dados do lead
            form_lead = LeadForm(instance=lead_selecionado)

    context = {
        'leads': leads_com_chat,
        'lead_selecionado': lead_selecionado,
        'mensagens': mensagens,
        'templates': templates,
        'form_lead': form_lead
    }
    return render(request, 'cadastros/leads/caixa_de_entrada.html', context)


@login_required
@require_POST
def enviar_mensagem_api(request, lead_pk):
    """ Endpoint AJAX (Fetch) para o frontend enviar uma mensagem sem recarregar a página. """
    lead = get_object_or_404(Lead, pk=lead_pk)
    try:
        dados = json.loads(request.body)
        texto = dados.get('texto', '').strip()
        
        if not texto:
            return JsonResponse({'status': 'erro', 'mensagem': 'Texto vazio.'}, status=400)
        
        # Dispara via API da Meta
        sucesso, resposta = enviar_mensagem_whatsapp(lead, texto)
        
        if sucesso:
            return JsonResponse({'status': 'sucesso', 'mensagem': resposta})
        else:
            return JsonResponse({'status': 'erro', 'mensagem': resposta}, status=400)
            
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


@login_required
def buscar_mensagens_api(request, lead_pk):
    """ Endpoint AJAX (Polling) para o frontend procurar novas mensagens recebidas. """
    lead = get_object_or_404(Lead, pk=lead_pk)
    ultima_msg_id = int(request.GET.get('ultima_msg_id', 0))
    
    novas_mensagens = MensagemWhatsApp.objects.filter(
        lead=lead, 
        id__gt=ultima_msg_id
    ).order_by('data_envio')
    
    dados_mensagens = [{
        'id': msg.id,
        'direcao': msg.direcao,
        'conteudo_texto': msg.conteudo_texto,
        'data_envio': msg.data_envio.strftime('%H:%M'),
        'status': msg.get_status_display()
    } for msg in novas_mensagens]
    
    return JsonResponse({'status': 'sucesso', 'mensagens': dados_mensagens})