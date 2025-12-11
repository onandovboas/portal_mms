# cadastros/management/commands/gerar_cobrancas.py

from django.core.management.base import BaseCommand
from cadastros.models import Contrato, Pagamento
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Q # <--- Importante para o filtro OU
import calendar

class Command(BaseCommand):
    help = 'Gera as cobranças de mensalidade e matrícula para contratos ativos e trancados.'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        
        # --- ALTERAÇÃO PRINCIPAL AQUI ---
        # Buscamos contratos que estão marcados como ATIVOS no sistema
        # OU que estão com status 'trancado' (pois eles continuam gerando boleto)
        # Filtramos também pela data de vigência para não gerar boleto de contrato vencido
        
        criterio_vigencia = Q(data_inicio__lte=hoje) & (Q(data_fim__gte=hoje) | Q(data_fim__isnull=True))
        criterio_status = Q(ativo=True) | Q(status='trancado')

        contratos_para_processar = Contrato.objects.filter(criterio_vigencia & criterio_status)
        
        self.stdout.write(self.style.SUCCESS(f'Encontrados {len(contratos_para_processar)} contratos vigentes (Ativos ou Trancados).'))

        for contrato in contratos_para_processar:
            # ... (O restante do seu código permanece IDÊNTICO, pois a lógica de gerar é a mesma) ...
            self.stdout.write(f"\nVerificando contrato de {contrato.aluno.nome_completo}...")
            
            data_iteradora = contrato.data_inicio
            while data_iteradora.year < hoje.year or (data_iteradora.year == hoje.year and data_iteradora.month <= hoje.month):
                
                mes_corrente_loop = data_iteradora
                
                # --- LÓGICA DE STATUS (Mantida) ---
                status_pagamento = 'pendente'
                if mes_corrente_loop.year < hoje.year:
                    status_pagamento = 'atrasado'
                elif mes_corrente_loop.month < hoje.month:
                    status_pagamento = 'atrasado'

                if mes_corrente_loop.year < 2025 or (mes_corrente_loop.year == 2025 and mes_corrente_loop.month < 9):
                    status_pagamento = 'pago'
                
                # --- LÓGICA DA MENSALIDADE ---
                mensalidade_existente = Pagamento.objects.filter(contrato=contrato, tipo='mensalidade', mes_referencia__year=mes_corrente_loop.year, mes_referencia__month=mes_corrente_loop.month).exists()

                if not mensalidade_existente:
                    ultimo_dia = calendar.monthrange(mes_corrente_loop.year, mes_corrente_loop.month)[1]
                    data_venc = mes_corrente_loop.replace(day=ultimo_dia)
                    
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
                    self.stdout.write(f'  -> Mensalidade de {mes_corrente_loop.strftime("%m/%Y")} gerada.')

                # --- LÓGICA DA MATRÍCULA (Mantida) ---
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
                            self.stdout.write(f'  -> Parcela de matrícula gerada.')

                data_iteradora += relativedelta(months=1)

        self.stdout.write(self.style.SUCCESS('\nCobranças geradas com sucesso.'))