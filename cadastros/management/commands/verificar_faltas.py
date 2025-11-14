# cadastros/management/commands/verificar_faltas.py

from django.core.management.base import BaseCommand
from cadastros.models import Aluno, Inscricao, Presenca, AcompanhamentoFalta
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q # Importar o Q

class Command(BaseCommand):
    help = 'Verifica inscrições ativas por sequências de 3 ou mais faltas consecutivas NAQUELA TURMA.'

    def handle(self, *args, **options):
        CONSECUTIVE_ABSENCES_THRESHOLD = 3
        data_limite = timezone.now().date() - timedelta(days=30)
        
        # 1. Pega todas as INSCRIÇÕES ativas (matriculado, acompanhando, experimental)
        #    Usamos select_related para otimizar a busca do aluno e da turma.
        inscricoes_ativas = Inscricao.objects.filter(
            Q(status='matriculado') | Q(status='acompanhando') | Q(status='experimental')
        ).select_related('aluno', 'turma')

        self.stdout.write(self.style.SUCCESS(f'Iniciando verificação de faltas para {inscricoes_ativas.count()} inscrições ativas...'))

        # Criamos um set para rastrear alunos que já têm um alerta pendente
        # Isso evita que o script pule a verificação de uma turma 
        # só porque o aluno já tem um alerta (que pode ser de outra turma).
        alunos_com_alerta_pendente = set(
            AcompanhamentoFalta.objects.filter(status='pendente').values_list('aluno_id', flat=True)
        )

        for inscricao in inscricoes_ativas:
            aluno = inscricao.aluno
            turma = inscricao.turma

            # 2. Verifica se já existe um acompanhamento pendente para este aluno. Se sim, pula.
            #    (Mantemos esta lógica para não sobrecarregar o admin)
            if aluno.id in alunos_com_alerta_pendente:
                continue

            # 3. Pega todos os registros de presença do aluno, APENAS DA TURMA DA INSCRIÇÃO ATUAL.
            #    Esta é a mudança principal.
            presencas = Presenca.objects.filter(
                aluno=aluno,
                registro_aula__turma=turma, # <-- FILTRO ADICIONADO
                registro_aula__data_aula__gte=data_limite
            ).order_by('registro_aula__data_aula')

            consecutive_absences_counter = 0
            last_absence_date = None

            # 4. Itera sobre os registros de presença (lógica mantida)
            for presenca in presencas:
                if not presenca.presente:
                    consecutive_absences_counter += 1
                    last_absence_date = presenca.registro_aula.data_aula
                else:
                    consecutive_absences_counter = 0

                # 5. Se o contador atingir o limite, cria o alerta
                if consecutive_absences_counter >= CONSECUTIVE_ABSENCES_THRESHOLD:
                    # Cria o alerta
                    AcompanhamentoFalta.objects.create(
                        aluno=aluno,
                        data_inicio_sequencia=last_absence_date - timedelta(days=consecutive_absences_counter - 1),
                        numero_de_faltas=consecutive_absences_counter,
                        status='pendente'
                        # NOTA: O modelo AcompanhamentoFalta não tem relação com a Turma.
                        # Se isso for um problema, precisaríamos adicionar um ForeignKey no models.py
                    )
                    
                    self.stdout.write(self.style.WARNING(f'  -> Alerta de {consecutive_absences_counter} faltas (em {turma.nome}) criado para {aluno.nome_completo}.'))
                    
                    # Adiciona o aluno ao set para não criarmos mais alertas para ele nesta rodada
                    alunos_com_alerta_pendente.add(aluno.id)
                    
                    break # Vai para a próxima inscrição

        self.stdout.write(self.style.SUCCESS('Verificação de faltas finalizada.'))