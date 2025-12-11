# gestao_escola/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from cadastros import views # Mantenha esta linha se tiver views de login/logout aqui
from django.conf import settings # <--- IMPORTANTE
from django.conf.urls.static import static # <--- IMPORTANTE

urlpatterns = [
    path('admin/', admin.site.urls),

    # Rotas de Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='cadastros/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Inclui TODAS as outras URLs do seu app sob o prefixo '' (raiz do site)
    # Isso torna a gestão muito mais simples.
    path('', include('cadastros.urls', namespace='cadastros')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)