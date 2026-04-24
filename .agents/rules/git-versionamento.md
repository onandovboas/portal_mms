---
trigger: always_on
---

Branching: Nunca sugerir commits diretos na main. Funcionalidades novas devem ser propostas em feature/ e correções críticas em hotfix/.

Sincronização: Sempre incluir o passo de realizar o merge do hotfix de volta para a branch develop para manter as bases de código alinhadas.

Migrações: Relembrar a necessidade de python manage.py migrate sempre que houver alterações no models.py antes do reload do servidor.