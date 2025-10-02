# gestao_escola/urls.py
from django.contrib import admin
from django.urls import path, include # 👈 1. Importe o 'include'
from cadastros import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.portal_professor, name='home'),
    path('admin/', admin.site.urls),
    path('portal/', include('cadastros.urls')), # 👈 2. Adicione esta linha
    path('dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('login/', auth_views.LoginView.as_view(template_name='cadastros/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('acompanhamento/resolver/<int:pk>/', views.resolver_acompanhamento, name='resolver_acompanhamento'),
    path('lancamento/novo/', views.lancamento_recebimento, name='lancamento_recebimento'),
    path('venda/livro/', views.venda_livro, name='venda_livro'),
    path('relatorios/professores/', views.relatorio_pagamento_professores, name='relatorio_professores'),
]