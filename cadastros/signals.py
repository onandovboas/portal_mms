# cadastros/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Aluno, Inscricao
from django.db.models import Q # Importar o Q

@receiver(post_save, sender=Aluno)
def sincronizar_status_inscricao(sender, instance, created, **kwargs):
    """
    Quando um Aluno é atualizado (salvo), esta função é chamada.
    """
    
    # Ignora a lógica se for um Aluno recém-criado
    if created:
        return

    aluno = instance
    
    # Lista dos status que DEVEM ser replicados para as matrículas
    status_para_sincronizar = ['inativo', 'trancado']

    if aluno.status in status_para_sincronizar:
        
        # Encontra todas as inscrições deste aluno que NÃO ESTÃO
        # com o status de desistiu OU com o status final desejado.
        # (Não queremos "reativar" uma inscrição 'desistiu' para 'trancado', por exemplo)
        inscricoes_para_atualizar = Inscricao.objects.filter(
            aluno=aluno
        ).exclude(
            Q(status=aluno.status) | Q(status='desistiu')
        )
        
        # Atualiza todas de uma vez
        if inscricoes_para_atualizar.exists():
            inscricoes_para_atualizar.update(status=aluno.status)
            