import json
import requests
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Lead, MensagemWhatsApp

logger = logging.getLogger(__name__)

# Configurações da Meta (idealmente definidas no seu settings.py ou .env)
VERIFY_TOKEN = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'mms_portal_whatsapp_token')
ACCESS_TOKEN = getattr(settings, 'META_ACCESS_TOKEN', '')
PHONE_NUMBER_ID = getattr(settings, 'META_PHONE_NUMBER_ID', '')

def enviar_mensagem_whatsapp(lead, texto):
    """
    Função utilitária para disparar mensagens de texto de volta via Meta API.
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Formata o telefone removendo caracteres não numéricos
    telefone_destino = ''.join(filter(str.isdigit, lead.telefone))
    
    # A Meta exige o DDI (55 para Brasil)
    if not telefone_destino.startswith('55'):
        telefone_destino = f"55{telefone_destino}"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefone_destino,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": texto
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code == 200:
            wamid = response_data.get('messages', [{}])[0].get('id', '')
            # Regista a mensagem de saída no histórico do CRM
            MensagemWhatsApp.objects.create(
                lead=lead,
                direcao='saida',
                conteudo_texto=texto,
                wamid=wamid,
                status='enviado'
            )
            return True, "Mensagem enviada com sucesso"
        else:
            logger.error(f"Erro ao enviar WhatsApp: {response_data}")
            return False, response_data.get('error', {}).get('message', 'Erro desconhecido')
            
    except Exception as e:
        logger.error(f"Exceção ao enviar WhatsApp: {e}")
        return False, str(e)


@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook Oficial para receber atualizações e mensagens da Meta.
    """
    if request.method == 'GET':
        # Verificação inicial exigida pela Meta
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
        # Processamento das mensagens recebidas
        try:
            body = json.loads(request.body)
            print(json.dumps(body, indent=4))
            
            if body.get('object') == 'whatsapp_business_account':
                for entry in body.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        
                        # Verifica se há mensagens de texto
                        if 'messages' in value:
                            for msg in value['messages']:
                                if msg.get('type') == 'text':
                                    telefone_remetente = msg.get('from')
                                    texto_recebido = msg.get('text', {}).get('body', '')
                                    wamid = msg.get('id')
                                    nome_contato = value.get('contacts', [{}])[0].get('profile', {}).get('name', 'Contato Desconhecido')

                                    # Busca o Lead ou cria um novo (Lógica aprimorada)
                                    lead_telefone = telefone_remetente.replace('55', '', 1) if telefone_remetente.startswith('55') else telefone_remetente
                                    
                                    lead, created = Lead.objects.get_or_create(
                                        telefone__contains=lead_telefone[-8:], # Flexibilidade para DDI/DDD
                                        defaults={
                                            'nome_completo': nome_contato,
                                            'telefone': telefone_remetente,
                                            'status': 'novo',
                                            'fonte_contato': 'whatsapp',
                                            'observacoes': "Lead criado automaticamente via integração WhatsApp."
                                        }
                                    )

                                    # Regista a mensagem de entrada no histórico
                                    MensagemWhatsApp.objects.create(
                                        lead=lead,
                                        direcao='entrada',
                                        conteudo_texto=texto_recebido,
                                        wamid=wamid,
                                        status='entregue'
                                    )
                                    
            return HttpResponse('EVENT_RECEIVED', status=200)
            
        except json.JSONDecodeError:
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.error(f"Server Error no Webhook: {e}")
            return HttpResponse('Server Error', status=500)
    
    return HttpResponse('Method not allowed', status=405)