from django.apps import AppConfig


class CadastrosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cadastros'

    def ready(self):
        # Esta linha importa os nossos sinais assim que o Django inicia
        import cadastros.signals
