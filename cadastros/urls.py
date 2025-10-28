# cadastros/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .forms import MyPasswordChangeForm

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
    path('aluno/atualizar/<uuid:token>/', views.atualizar_dados_aluno, name='atualizar_dados_aluno'),
    path('contrato/<int:contrato_pk>/editar/', views.editar_contrato, name='editar_contrato'),

    # Rotas Acompanhamentos Pedagogicos
    path('acompanhamento-pedagogico/', views.lista_acompanhamento_pedagogico, name='lista_acompanhamento_pedagogico'),
    path('aluno/<int:aluno_pk>/acompanhamento/novo/', views.adicionar_acompanhamento, name='adicionar_acompanhamento'),
    path('acompanhamento/<int:pk>/editar/', views.editar_acompanhamento, name='editar_acompanhamento'),
    path('aluno/<int:aluno_pk>/acompanhamentos/', views.historico_acompanhamentos_aluno, name='historico_acompanhamentos_aluno'),

    # Rotas Portal Aluno
    path('portal/', views.portal_aluno, name='portal_aluno'),
    path('portal/login/', views.portal_login_view, name='portal_login'),
    path('portal/logout/', auth_views.LogoutView.as_view(next_page='cadastros:portal_login'), name='portal_logout'),
    path('aluno/<int:aluno_pk>/criar-acesso/', views.criar_acesso_portal, name='criar_acesso_portal'),
    path('portal/mudar-senha/', auth_views.PasswordChangeView.as_view(
        template_name='cadastros/password_change_form.html',
        success_url='/portal/mudar-senha/concluido/',
        form_class=MyPasswordChangeForm # ✅ ADICIONE ESTA LINHA ✅
    ), name='password_change'),
    path('portal/mudar-senha/concluido/', auth_views.PasswordChangeDoneView.as_view(
        template_name='cadastros/password_change_done.html'
    ), name='password_change_done'),
    path('aluno/<int:aluno_pk>/redefinir-senha/', views.redefinir_senha_aluno, name='redefinir_senha_aluno'),

    # Rotas para Provas
    path('aluno/<int:aluno_pk>/liberar-prova/', views.liberar_prova, name='liberar_prova'),
    path('turma/<int:turma_pk>/liberar-prova/', views.liberar_prova_turma, name='liberar_prova_turma'),
    path('portal/prova/<int:aluno_prova_pk>/iniciar/', views.iniciar_prova, name='iniciar_prova'),
    path('portal/prova/<int:aluno_prova_pk>/secao/<int:secao_num>/', views.realizar_prova_secao, name='realizar_prova_secao'),
    path('portal/prova/<int:aluno_prova_pk>/concluida/', views.prova_concluida, name='prova_concluida'),
    path('prova/correcao/<int:aluno_prova_pk>/', views.corrigir_prova, name='corrigir_prova'),
    path('prova/resultado/<int:aluno_prova_pk>/', views.ver_resultado_prova, name='ver_resultado_prova'),
    path('prova-template/<int:pk>/copiar/', views.copiar_prova_template, name='copiar_prova_template'),



    # Rota para Leads
    path('leads/', views.lista_leads, name='lista_leads'),
    path('leads/adicionar/', views.adicionar_lead, name='adicionar_lead'), 
    path('leads/<int:pk>/editar/', views.editar_lead, name='editar_lead'),
    path('leads/<int:pk>/converter/', views.converter_lead, name='converter_lead'),
    path('inscricao/<int:inscricao_pk>/desistiu/', views.marcar_experimental_desistiu, name='marcar_experimental_desistiu'),
    path('leads/atualizar-status/', views.atualizar_status_lead, name='atualizar_status_lead'),

    # Rotas de Turmas
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
    path('aluno/<int:aluno_pk>/gerar-link/', views.gerar_link_atualizacao, name='gerar_link_atualizacao'),


    # Rotas para Exportação
    path('exportar/', views.exportar_dados_page, name='exportar_dados_page'),
    path('exportar/contratos/', views.exportar_contratos_csv, name='exportar_contratos_csv'),
    path('exportar/pagamentos/', views.exportar_pagamentos_csv, name='exportar_pagamentos_csv'),
    path('exportar/registros-aula-por-turma/', views.exportar_registros_aula_por_turma_zip, name='exportar_registros_aula_por_turma_zip'),
    
    # Relatórios
    path('relatorios/professores/', views.relatorio_pagamento_professores, name='relatorio_professores'),
    path('relatorios/alunos-pendentes/', views.relatorio_alunos_pendentes, name='relatorio_alunos_pendentes'),

]