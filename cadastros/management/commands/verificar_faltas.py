# cadastros/management/commands/verificar_faltas.py

from django.core.management.base import BaseCommand
from cadastros.models import Aluno, Inscricao, Presenca, AcompanhamentoFalta
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Gere o ciclo de vida de faltas: cria novos alertas, atualiza contadores ou remove alertas se houver presença.'

    def handle(self, *args, **options):
        CONSECUTIVE_ABSENCES_THRESHOLD = 3
        data_limite = timezone.now().date() - timedelta(days=30)
        
        # 1. Filtramos apenas inscrições de quem está MATRICULADO
        inscricoes_ativas = Inscricao.objects.filter(
            status='matriculado' 
        ).select_related('aluno', 'turma')

        self.stdout.write(self.style.SUCCESS(f'Iniciando processamento de faltas...'))

        for inscricao in inscricoes_ativas:
            # Reforço de segurança: garante que ignoramos 'acompanhando' ou 'experimental'
            if inscricao.status != 'matriculado':
                continue

            aluno = inscricao.aluno
            turma = inscricao.turma

            # O filtro de presenças foca estritamente na turma de matrícula do aluno
            presencas = Presenca.objects.filter(
                aluno=aluno,
                registro_aula__turma=turma,
                registro_aula__data_aula__gte=data_limite
            ).order_by('-registro_aula__data_aula')

            # 2. Verifica a situação atual (Presença ou Falta na última aula registrada)
            ultima_presenca = presencas.first()
            alerta_pendente = AcompanhamentoFalta.objects.filter(aluno=aluno, status='pendente').first()

            # TAREFA 2: Se o aluno teve presença e tinha um alerta, resolvemos automaticamente
            if ultima_presenca and ultima_presenca.presente and alerta_pendente:
                alerta_pendente.status = 'resolvido'
                alerta_pendente.motivo = f"Resolvido automaticamente: Presença detectada em {ultima_presenca.registro_aula.data_aula.strftime('%d/%m/%Y')}."
                alerta_pendente.data_resolucao = timezone.now()
                alerta_pendente.save()
                self.stdout.write(self.style.SUCCESS(f'  -> Alerta RESOLVIDO para {aluno.nome_completo} (Voltou às aulas).'))
                continue

            # 3. Cálculo de faltas consecutivas (da mais nova para mais antiga)
            consecutive_absences_counter = 0
            data_primeira_falta_na_sequencia = None

            for p in presencas:
                if not p.presente:
                    consecutive_absences_counter += 1
                    data_primeira_falta_na_sequencia = p.registro_aula.data_aula
                else:
                    break 

            # TAREFA 1 & 2: Gestão de Alertas (Criar ou Atualizar)
            if consecutive_absences_counter >= CONSECUTIVE_ABSENCES_THRESHOLD:
                
                if alerta_pendente:
                    # Se o número de faltas aumentou, atualizamos o registro existente
                    if consecutive_absences_counter > alerta_pendente.numero_de_faltas:
                        alerta_pendente.numero_de_faltas = consecutive_absences_counter
                        alerta_pendente.save()
                        self.stdout.write(self.style.WARNING(f'  -> Alerta ATUALIZADO: {aluno.nome_completo} agora com {consecutive_absences_counter} faltas.'))
                else:
                    # Se não existe alerta pendente, criamos um novo
                    AcompanhamentoFalta.objects.get_or_create(
                        aluno=aluno,
                        data_inicio_sequencia=data_primeira_falta_na_sequencia,
                        status='pendente',
                        defaults={'numero_de_faltas': consecutive_absences_counter}
                    )
                    self.stdout.write(self.style.WARNING(f'  -> NOVO Alerta: {aluno.nome_completo} atingiu {consecutive_absences_counter} faltas.'))

        self.stdout.write(self.style.SUCCESS('Processamento finalizado.'))