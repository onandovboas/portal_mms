---
trigger: always_on
---

Para manter o sistema estável no PythonAnywhere, a IA deve seguir estas diretrizes técnicas:

Injeção de Dados em JS: Proibir o uso de loops {% for %} dentro de blocos <script>. Utilizar obrigatoriamente o filtro |json_script e ler via JSON.parse para evitar erros de renderização.


Consultas Otimizadas: Utilizar Exists() ou Subquery em listagens (como a lista_alunos) para evitar o problema de performance N+1 ao verificar feedbacks.


Estáticos e Mídia: Utilizar sempre STATICFILES_DIRS para arquivos locais e garantir que novas funcionalidades de imagem respeitem a configuração de MEDIA_ROOT para fotos de perfil.