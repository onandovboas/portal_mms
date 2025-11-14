# cadastros/decorators.py
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    """
    Verifica se o usuário é um Administrador (staff).
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Acesso negado. Esta área é restrita a administradores.")
            # Redireciona para o portal correto se ele não for admin
            if hasattr(request.user, 'perfil_aluno'):
                return redirect('cadastros:portal_aluno')
            if hasattr(request.user, 'professor'):
                return redirect('cadastros:portal_professor')
            return redirect('cadastros:login') # Fallback
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def professor_required(view_func):
    """
    Verifica se o usuário é um Professor.
    (Também permite acesso de Admins)
    """
    def _wrapped_view(request, *args, **kwargs):
        # Admin pode ver as páginas do professor
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        if not hasattr(request.user, 'professor'):
            messages.error(request, "Acesso negado. Esta área é restrita a professores.")
            if hasattr(request.user, 'perfil_aluno'):
                return redirect('cadastros:portal_aluno')
            return redirect('cadastros:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def aluno_required(view_func):
    """
    Verifica se o usuário é um Aluno.
    (Admins NÃO devem acessar, pois a view depende de request.user.perfil_aluno)
    """
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'perfil_aluno'):
            messages.error(request, "Acesso negado. Esta área é restrita a alunos.")
            if hasattr(request.user, 'professor'):
                return redirect('cadastros:portal_professor')
            if request.user.is_staff:
                # Redireciona admin para o dashboard, pois portal_aluno falharia
                return redirect('cadastros:dashboard_admin')
            return redirect('cadastros:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view