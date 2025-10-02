# cadastros/management/commands/verificar_faltas.py

from django.core.management.base import BaseCommand
from cadastros.models import Aluno, Inscricao, Presenca, AcompanhamentoFalta
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Verifica todos os alunos ativos por sequências de 3 ou mais faltas consecutivas.'

    def handle(self, *args, **options):
        CONSECUTIVE_ABSENCES_THRESHOLD = 3
        # Vamos verificar os últimos 30 dias para performance
        data_limite = timezone.now().date() - timedelta(days=30)
        
        # 1. Pega todos os alunos que estão com matrícula ativa.
        inscricoes_ativas = Inscricao.objects.filter(status='matriculado')
        alunos_a_verificar = [inscricao.aluno for inscricao in inscricoes_ativas]

        self.stdout.write(self.style.SUCCESS(f'Iniciando verificação de faltas para {len(alunos_a_verificar)} alunos ativos...'))

        for aluno in alunos_a_verificar:
            # 2. Verifica se já existe um acompanhamento pendente para este aluno. Se sim, pula para o próximo.
            if AcompanhamentoFalta.objects.filter(aluno=aluno, status='pendente').exists():
                continue

            # 3. Pega todos os registros de presença do aluno no período, ordenados por data.
            presencas = Presenca.objects.filter(
                aluno=aluno,
                registro_aula__data_aula__gte=data_limite
            ).order_by('registro_aula__data_aula')

            consecutive_absences_counter = 0
            last_absence_date = None

            # 4. Itera sobre os registros de presença para encontrar uma sequência.
            for presenca in presencas:
                if not presenca.presente:
                    # Se faltou, incrementa o contador.
                    consecutive_absences_counter += 1
                    last_absence_date = presenca.registro_aula.data_aula
                else:
                    # Se veio na aula, zera o contador.
                    consecutive_absences_counter = 0

                # 5. Se o contador atingir o limite, cria o alerta e para de verificar este aluno.
                if consecutive_absences_counter >= CONSECUTIVE_ABSENCES_THRESHOLD:
                    AcompanhamentoFalta.objects.create(
                        aluno=aluno,
                        data_inicio_sequencia=last_absence_date - timedelta(days=consecutive_absences_counter - 1),
                        numero_de_faltas=consecutive_absences_counter,
                        status='pendente'
                    )
                    self.stdout.write(self.style.WARNING(f'  -> Alerta de {consecutive_absences_counter} faltas criado para {aluno.nome_completo}.'))
                    break # Vai para o próximo aluno

        self.stdout.write(self.style.SUCCESS('Verificação de faltas finalizada.'))