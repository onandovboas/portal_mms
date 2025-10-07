# cadastros/urls.py

from django.urls import path
from . import views

app_name = 'cadastros'

urlpatterns = [
    # Rotas principais da Aplicação
    path('', views.portal_professor, name='portal_professor'),
    path('dashboard/', views.dashboard_admin, name='dashboard_admin'),

    # Rotas de Alunos
    path('aluno/<int:pk>/', views.perfil_aluno, name='perfil_aluno'),
    path("aluno/<int:pk>/editar/", views.editar_aluno, name="editar_aluno"),
    path("aluno/<int:pk>/exportar-pagamentos/", views.exportar_pagamentos_aluno, name="exportar_pagamentos_aluno"),
    path("aluno/<int:pk>/pagamentos/novo/", views.novo_pagamento, name="novo_pagamento"),
    path('alunos/', views.lista_alunos, name='lista_alunos'),
    path('aluno/<int:pk>/quitar-dividas/', views.quitar_dividas_aluno, name='quitar_dividas_aluno'),
    path('aluno/novo-experimental/', views.novo_aluno_experimental, name='novo_aluno_experimental'),
    path('aluno/<int:aluno_pk>/criar-contrato/', views.criar_contrato, name='criar_contrato'),

    #Rotas de Turmas
    path('turma/<int:pk>/', views.detalhe_turma, name='detalhe_turma'),
    path('registro-aula/editar/<int:pk>/', views.editar_registro_aula, name='editar_registro_aula'),

    # Rotas financeiras e administrativas
    path('acompanhamento/resolver/<int:pk>/', views.resolver_acompanhamento, name='resolver_acompanhamento'),
    path('lancamento/novo/', views.lancamento_recebimento, name='lancamento_recebimento'),
    path('venda/livro/', views.venda_livro, name='venda_livro'),
    path('pagamentos/bulk/', views.pagamentos_bulk, name='pagamentos_bulk'),
    path('pagamentos/acoes-em-lote/', views.pagamentos_acoes_em_lote, name='pagamentos_acoes_em_lote'),
    path('inscricao/', views.formulario_inscricao, name='formulario_inscricao'),
    path('pagamento/quitar/<int:pk>/', views.quitar_pagamento_especifico, name='quitar_pagamento'),
    path('pagamento/editar/<int:pk>/', views.editar_pagamento, name='editar_pagamento'),


    
    
    # Relatórios
    path('relatorios/professores/', views.relatorio_pagamento_professores, name='relatorio_professores'),
    path('relatorios/alunos-pendentes/', views.relatorio_alunos_pendentes, name='relatorio_alunos_pendentes'),

]