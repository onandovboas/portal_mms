import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Lead

# Obtenha o token de verificação (pode ser definido no .env)
# Para teste, usaremos uma string fixa se não estiver no settings
VERIFY_TOKEN = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'mms_portal_whatsapp_token')

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        # Verificação do Webhook pela Meta
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return HttpResponse(challenge, status=200)
            else:
                return HttpResponse('Token inválido', status=403)
        return HttpResponse('Requisição inválida', status=400)

    elif request.method == 'POST':
        # Recebimento de mensagens
        try:
            body = json.loads(request.body)
            # Verifica se é um evento do WhatsApp Business Account
            if body.get('object') == 'whatsapp_business_account':
                for entry in body.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        messages = value.get('messages', [])
                        contacts = value.get('contacts', [])
                        
                        if messages and contacts:
                            message = messages[0]
                            contact = contacts[0]
                            
                            telefone = message.get('from') # O número de telefone do remetente
                            nome = contact.get('profile', {}).get('name', 'Contato Desconhecido')
                            
                            # Verifica se o Lead já existe
                            if not Lead.objects.filter(telefone=telefone).exists():
                                Lead.objects.create(
                                    nome_completo=nome,
                                    telefone=telefone,
                                    status='novo',
                                    fonte_contato='whatsapp',
                                    observacoes="Lead criado automaticamente via integração WhatsApp."
                                )
            return HttpResponse('EVENT_RECEIVED', status=200)
        except json.JSONDecodeError:
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            return HttpResponse('Server Error', status=500)
    
    return HttpResponse('Method not allowed', status=405)
