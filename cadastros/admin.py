# cadastros/admin.py

from django.contrib import admin
from .models import (
    Aluno, Professor, Turma, Inscricao, RegistroAula, Presenca, 
    Contrato, Pagamento, AcompanhamentoFalta, HorarioAula, ProvaTemplate, Questao, AlunoProva
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

class QuestaoInline(admin.StackedInline):
    """Permite adicionar e editar Questões diretamente na página do ProvaTemplate."""
    model = Questao
    extra = 1  # Mostra 1 formulário em branco para adicionar uma nova questão.
    fields = ('ordem', 'tipo_questao', 'enunciado', 'pontos', 'dados_questao')
    ordering = ('ordem',)


@admin.register(ProvaTemplate)
class ProvaTemplateAdmin(admin.ModelAdmin):
    """Configuração da admin para os Gabaritos de Prova."""
    list_display = ('titulo', 'stage_referencia')
    inlines = [QuestaoInline]  # A mágica acontece aqui!
    search_fields = ['titulo']
    list_filter = ['stage_referencia']


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    """Permite gerir todas as questões de forma individual (opcional)."""
    list_display = ('__str__', 'prova_template', 'tipo_questao', 'pontos')
    list_filter = ('prova_template', 'tipo_questao')


@admin.register(AlunoProva)
class AlunoProvaAdmin(admin.ModelAdmin):
    """Configuração da admin para visualizar as Provas dos Alunos."""
    list_display = ('aluno', 'prova_template', 'status', 'nota_final', 'data_realizacao')
    list_filter = ('status', 'prova_template__stage_referencia', 'aluno')
    search_fields = ('aluno__nome_completo', 'prova_template__titulo')
    autocomplete_fields = ['aluno', 'prova_template'] # Facilita a seleção


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