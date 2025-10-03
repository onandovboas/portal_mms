# cadastros/admin.py

from django.contrib import admin
from .models import (
    Aluno, Professor, Turma, Inscricao, RegistroAula, Presenca, 
    Contrato, Pagamento, AcompanhamentoFalta, HorarioAula
)

class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 1


class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'email', 'status')
    search_fields = ['nome_completo', 'email']
    list_filter = ['status']

class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'aluno', 'valor', 'status', 'data_vencimento')
    list_filter = ('status', 'tipo', 'mes_referencia')
    search_fields = ('aluno__nome_completo', 'descricao')

class HorarioAulaInline(admin.TabularInline):
    model = HorarioAula
    extra = 1  # Quantos formulários em branco exibir
    fields = ('dia_semana', 'horario_inicio', 'horario_fim') # Campos a serem exibidos

class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 1

class TurmaAdmin(admin.ModelAdmin):
    # 2. Adicionar o HorarioAulaInline aqui
    inlines = [HorarioAulaInline, InscricaoInline]
    list_display = ('nome', 'stage')
    search_fields = ['nome']


class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'aluno', 'valor', 'status', 'data_vencimento')
    list_filter = ('status', 'tipo', 'mes_referencia')
    search_fields = ('aluno__nome_completo', 'descricao')

# Registra os modelos no site de administração.
admin.site.register(Aluno, AlunoAdmin)
admin.site.register(Professor)
admin.site.register(Turma, TurmaAdmin)
admin.site.register(Inscricao)
admin.site.register(RegistroAula)
admin.site.register(Presenca)
admin.site.register(Contrato) 
admin.site.register(Pagamento, PagamentoAdmin)
admin.site.register(AcompanhamentoFalta)
admin.site.register(HorarioAula)