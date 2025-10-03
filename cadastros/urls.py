# cadastros/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_professor, name='portal_professor'),
    path('turma/<int:pk>/', views.detalhe_turma, name='detalhe_turma'),
    path('pagamentos/bulk/', views.pagamentos_bulk, name='pagamentos_bulk'),
    # As linhas de login e logout foram REMOVIDAS daqui
    path("aluno/<int:pk>/", views.perfil_aluno, name="perfil_aluno"),
    path("aluno/<int:pk>/editar/", views.editar_aluno, name="editar_aluno"),
    path("aluno/<int:pk>/pagamentos/novo/", views.novo_pagamento, name="novo_pagamento"),
    path("aluno/<int:pk>/exportar-pagamentos/", views.exportar_pagamentos_aluno, name="exportar_pagamentos_aluno"),

]