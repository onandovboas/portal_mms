# cadastros/management/commands/verificar_faltas.py

from django.core.management.base import BaseCommand
from cadastros.models import Aluno, Inscricao, Presenca, AcompanhamentoFalta
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

class Command(BaseCommand):
    help = 'Verifica inscrições ativas por sequências de 3 ou mais faltas RECENTES.'

    def handle(self, *args, **options):
        CONSECUTIVE_ABSENCES_THRESHOLD = 3
        # Continuamos a usar 30 dias como limite de busca
        data_limite = timezone.now().date() - timedelta(days=30)
        
        inscricoes_ativas = Inscricao.objects.filter(
            Q(status='matriculado') | Q(status='acompanhando') | Q(status='experimental')
        ).select_related('aluno', 'turma')

        self.stdout.write(self.style.SUCCESS(f'Iniciando verificação de faltas para {inscricoes_ativas.count()} inscrições ativas...'))

        # Busca de alunos que JÁ TÊM um alerta pendente (para não duplicar)
        alunos_com_alerta_pendente = set(
            AcompanhamentoFalta.objects.filter(status='pendente').values_list('aluno_id', flat=True)
        )

        for inscricao in inscricoes_ativas:
            aluno = inscricao.aluno
            turma = inscricao.turma

            # 1. Se o aluno já tem um alerta PENDENTE, pulamos
            if aluno.id in alunos_com_alerta_pendente:
                continue

            # 2. Pega as presenças, DA MAIS RECENTE PARA A MAIS ANTIGA
            presencas = Presenca.objects.filter(
                aluno=aluno,
                registro_aula__turma=turma,
                registro_aula__data_aula__gte=data_limite
            ).order_by('-registro_aula__data_aula') # <--- MUDANÇA CRUCIAL: Ordem descendente

            consecutive_absences_counter = 0
            data_primeira_falta_na_sequencia = None # A mais antiga

            # 3. Itera do mais novo para o mais antigo
            for presenca in presencas:
                if not presenca.presente:
                    # Se faltou, incrementa o contador
                    consecutive_absences_counter += 1
                    # A "data de início" (a mais antiga) será a última que encontrarmos
                    data_primeira_falta_na_sequencia = presenca.registro_aula.data_aula
                else:
                    # Se encontrou uma presença, a sequência quebrou.
                    # Como estamos a ver do mais novo para o mais antigo,
                    # podemos parar imediatamente.
                    break 

            # 4. Só analisamos DEPOIS que o loop terminar
            if consecutive_absences_counter >= CONSECUTIVE_ABSENCES_THRESHOLD:
                # O aluno tem 3+ faltas consecutivas *recentes*
                
                # 5. VERIFICAÇÃO FINAL: Já existe um alerta (pendente OU resolvido)
                #    para esta sequência exata de faltas?
                #    (Usamos a data da primeira falta para identificar a sequência)
                
                if not AcompanhamentoFalta.objects.filter(
                    aluno=aluno,
                    data_inicio_sequencia=data_primeira_falta_na_sequencia
                ).exists():
                    
                    # Não existe! Criamos um novo alerta.
                    AcompanhamentoFalta.objects.create(
                        aluno=aluno,
                        data_inicio_sequencia=data_primeira_falta_na_sequencia,
                        numero_de_faltas=consecutive_absences_counter,
                        status='pendente'
                    )
                    self.stdout.write(self.style.WARNING(f'  -> Alerta de {consecutive_absences_counter} faltas RECENTES criado para {aluno.nome_completo}.'))
                    # Adiciona ao set para não criar outro alerta (ex: se ele estiver em 2 turmas)
                    alunos_com_alerta_pendente.add(aluno.id)

        self.stdout.write(self.style.SUCCESS('Verificação de faltas finalizada.'))