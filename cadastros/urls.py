# cadastros/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_professor, name='portal_professor'),
    path('turma/<int:pk>/', views.detalhe_turma, name='detalhe_turma'),
    path('pagamentos/bulk/', views.pagamentos_bulk, name='pagamentos_bulk'),
    # As linhas de login e logout foram REMOVIDAS daqui
]