# cadastros/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Aluno, Inscricao
from django.db.models import Q 
from django.contrib.auth.models import User # <-- Novo import para a criação de usuários

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

# ==============================================================================
# NOVA AUTOMAÇÃO: Criação automática de Usuário para novos Alunos
# ==============================================================================
@receiver(post_save, sender=Aluno)
def criar_usuario_aluno(sender, instance, created, **kwargs):
    """
    Cria um User automaticamente quando um novo Aluno é cadastrado.
    """
    # Só executa se o Aluno acabou de ser criado E ainda não tem um usuário vinculado
    if created and not instance.usuario:
        
        # Usa o e-mail como username. Se por acaso não tiver e-mail, cria um ID temporário.
        username_base = instance.email if instance.email else f"aluno_{instance.id}"
        
        # Garante que não vai tentar criar um username que já existe
        if not User.objects.filter(username=username_base).exists():
            novo_usuario = User.objects.create_user(
                username=username_base,
                email=instance.email,
                password='mudar@123' # Senha padrão inicial
            )
            
            # Vincula o novo usuário ao perfil do aluno e salva sem disparar os signals novamente em loop
            Aluno.objects.filter(pk=instance.pk).update(usuario=novo_usuario)