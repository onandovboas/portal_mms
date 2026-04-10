import csv
from django.core.management.base import BaseCommand
from cadastros.models import Aluno, ProvaTemplate, Questao, AlunoProva, RespostaAluno

class Command(BaseCommand):
    help = 'Importa as respostas da Prova (Stage 6) com busca exata por E-mail'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='O caminho absoluto ou relativo para o arquivo CSV')
        parser.add_argument('--template_id', type=int, help='ID do ProvaTemplate no banco de dados')

    def handle(self, *args, **kwargs):
        csv_path = kwargs['csv_path']
        template_id = kwargs.get('template_id')

        # 1. Busca o Template e as Questões
        prova_template = ProvaTemplate.objects.get(id=template_id) if template_id else ProvaTemplate.objects.first()
        questoes_banco = list(Questao.objects.filter(prova_template=prova_template).order_by('id'))

        if not questoes_banco:
            self.stdout.write(self.style.ERROR('Erro: O ProvaTemplate selecionado não possui questões cadastradas.'))
            return

        with open(csv_path, mode='r', encoding='utf-8') as arquivo_csv:
            leitor = csv.reader(arquivo_csv)
            cabecalhos = next(leitor)

            for index, linha in enumerate(leitor, start=2):
                if not linha: continue
                
                # ⚙️ ATENÇÃO AOS ÍNDICES:
                # Verifique em qual coluna o E-mail está caindo no seu novo CSV exportado!
                # Se o Carimbo de data/hora é linha[0] e o E-mail é a próxima, então é linha[1].
                email_forms = linha[1].strip() 
                
                # Ajuste os índices abaixo conforme a nova estrutura do seu CSV
                dictation = linha[3] 
                respostas_objetivas = linha[4:] 

                # 2. BUSCA EXATA PELO E-MAIL (Ignora maiúsculas/minúsculas com iexact)
                aluno = Aluno.objects.filter(email__iexact=email_forms).first()

                if not aluno:
                    self.stdout.write(self.style.ERROR(f'Linha {index}: Aluno com e-mail "{email_forms}" não encontrado no banco. Pulando.'))
                    continue

                # 3. Continua com a criação do AlunoProva e RespostaAluno
                aluno_prova, created = AlunoProva.objects.get_or_create(
                    aluno=aluno,
                    prova_template=prova_template,
                    defaults={'status': 'aguardando_correcao'}
                )
                
                if not created:
                    self.stdout.write(self.style.WARNING(f'Linha {index}: Prova já existia para {aluno.nome_completo}. Sobrescrevendo respostas...'))

                # 4. Salvar o Dictation
                if len(questoes_banco) > 0:
                    RespostaAluno.objects.update_or_create(
                        aluno_prova=aluno_prova,
                        questao=questoes_banco[0],
                        defaults={'resposta_texto': dictation} 
                    )

                # 5. Salvar as demais respostas
                for i, resposta_texto in enumerate(respostas_objetivas):
                    questao_index = i + 1 
                    
                    if questao_index < len(questoes_banco):
                        questao_atual = questoes_banco[questao_index]
                        
                        RespostaAluno.objects.update_or_create(
                            aluno_prova=aluno_prova,
                            questao=questao_atual,
                            defaults={'resposta_texto': resposta_texto.strip()}
                        )

                self.stdout.write(self.style.SUCCESS(f'Linha {index}: Prova de {aluno.nome_completo} importada com sucesso!'))