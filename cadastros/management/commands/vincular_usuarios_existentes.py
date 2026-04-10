from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from cadastros.models import Aluno

class Command(BaseCommand):
    help = 'Cria e vincula um User para alunos que já estão cadastrados no portal'

    def handle(self, *args, **kwargs):
        # 1. Filtra apenas alunos que não possuem usuário vinculado
        alunos_sem_user = Aluno.objects.filter(usuario__isnull=True)
        
        count = 0
        for aluno in alunos_sem_user:
            # Definimos o username como o e-mail ou uma versão do nome se o e-mail faltar
            username = aluno.email if aluno.email else f"aluno_{aluno.id}"
            
            # 2. Verifica se o User já existe (para evitar erro de duplicidade)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': aluno.email if aluno.email else '',
                    'first_name': aluno.nome_completo.split()[0] if aluno.nome_completo else ''
                }
            )

            # 3. Define uma senha padrão se o usuário acabou de ser criado
            if created:
                user.set_password('mms12345') # Senha inicial padrão
                user.save()

            # 4. Faz o vínculo no modelo Aluno
            aluno.usuario = user
            aluno.save()
            count += 1
            self.stdout.write(self.style.SUCCESS(f'Usuário {username} vinculado ao aluno {aluno.nome_completo}'))

        self.stdout.write(self.style.SUCCESS(f'Processo concluído! {count} alunos foram vinculados.'))