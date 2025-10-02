# cadastros/management/commands/gerar_cobrancas.py

from django.core.management.base import BaseCommand
from cadastros.models import Contrato, Pagamento
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import calendar

class Command(BaseCommand):
    help = 'Gera as cobranças de mensalidade e matrícula para todos os contratos ativos, incluindo as retroativas.'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        
        contratos_ativos = list(Contrato.objects.filter(
            ativo=True, data_inicio__lte=hoje, data_fim__gte=hoje
        )) + list(Contrato.objects.filter(
            ativo=True, data_inicio__lte=hoje, data_fim__isnull=True
        ))
        
        self.stdout.write(self.style.SUCCESS(f'Encontrados {len(contratos_ativos)} contratos para verificação.'))

        for contrato in contratos_ativos:
            self.stdout.write(f"\nVerificando contrato de {contrato.aluno.nome_completo}...")
            
            data_iteradora = contrato.data_inicio
            while data_iteradora.year < hoje.year or (data_iteradora.year == hoje.year and data_iteradora.month <= hoje.month):
                
                mes_corrente_loop = data_iteradora
                
                # --- NOVA LÓGICA DE STATUS ---
                # Define o status baseado na data
                status_pagamento = 'pendente' # Padrão para o mês atual
                if mes_corrente_loop.year < hoje.year:
                    status_pagamento = 'atrasado'
                elif mes_corrente_loop.month < hoje.month:
                    status_pagamento = 'atrasado'

                # Sua nova regra: marcar como 'pago' se for antes de Setembro de 2025
                if mes_corrente_loop.year < 2025 or (mes_corrente_loop.year == 2025 and mes_corrente_loop.month < 9):
                    status_pagamento = 'pago'
                
                # --- LÓGICA DA MENSALIDADE ---
                mensalidade_existente = Pagamento.objects.filter(contrato=contrato, tipo='mensalidade', mes_referencia__year=mes_corrente_loop.year, mes_referencia__month=mes_corrente_loop.month).exists()

                if not mensalidade_existente:
                    ultimo_dia = calendar.monthrange(mes_corrente_loop.year, mes_corrente_loop.month)[1]
                    data_venc = mes_corrente_loop.replace(day=ultimo_dia)
                    
                    # Se o status for 'pago', também preenchemos a data de pagamento
                    data_pgto = data_venc if status_pagamento == 'pago' else None
                    
                    Pagamento.objects.create(
                        aluno=contrato.aluno, contrato=contrato, tipo='mensalidade',
                        descricao=f"Mensalidade {mes_corrente_loop.strftime('%B/%Y')}",
                        valor=contrato.valor_mensalidade, mes_referencia=mes_corrente_loop,
                        data_vencimento=data_venc, 
                        status=status_pagamento,
                        data_pagamento=data_pgto,
                        valor_pago=contrato.valor_mensalidade if status_pagamento == 'pago' else 0
                    )
                    self.stdout.write(f'  -> Mensalidade de {mes_corrente_loop.strftime("%m/%Y")} gerada com status: {status_pagamento}.')

                # --- LÓGICA DA MATRÍCULA ---
                if contrato.valor_matricula > 0 and contrato.parcelas_matricula > 0:
                    parcelas_geradas = Pagamento.objects.filter(contrato=contrato, tipo='matricula').count()
                    if parcelas_geradas < contrato.parcelas_matricula:
                        parcela_existente_mes = Pagamento.objects.filter(contrato=contrato, tipo='matricula', mes_referencia__year=mes_corrente_loop.year, mes_referencia__month=mes_corrente_loop.month).exists()
                        if not parcela_existente_mes:
                            ultimo_dia = calendar.monthrange(mes_corrente_loop.year, mes_corrente_loop.month)[1]
                            data_venc = mes_corrente_loop.replace(day=ultimo_dia)
                            valor_parcela = round(contrato.valor_matricula / contrato.parcelas_matricula, 2)
                            data_pgto_mat = data_venc if status_pagamento == 'pago' else None

                            Pagamento.objects.create(
                                aluno=contrato.aluno, contrato=contrato, tipo='matricula',
                                descricao=f"Parcela {parcelas_geradas + 1}/{contrato.parcelas_matricula} Matrícula",
                                valor=valor_parcela, mes_referencia=mes_corrente_loop,
                                data_vencimento=data_venc,
                                status=status_pagamento,
                                data_pagamento=data_pgto_mat,
                                valor_pago=valor_parcela if status_pagamento == 'pago' else 0
                            )
                            self.stdout.write(f'  -> Parcela de matrícula {parcelas_geradas + 1} gerada com status: {status_pagamento}.')

                data_iteradora += relativedelta(months=1)

        self.stdout.write(self.style.SUCCESS('\nProcesso de geração de cobranças finalizado.'))