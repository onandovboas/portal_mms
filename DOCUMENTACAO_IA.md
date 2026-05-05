# Documentação do MMS Portal (Guia para IAs)

Este documento foi gerado para fornecer o contexto completo do projeto **MMS Portal** a qualquer nova inteligência artificial (ou desenvolvedor) que assumir o projeto. Leia este arquivo com atenção antes de iniciar novas features.

---

## 1. Visão Geral e Arquitetura
O MMS Portal é um sistema integrado de Gestão Pedagógica e CRM (Pipeline de Vendas) desenvolvido para gerenciar leads, alunos ativos, alunos trancados, disponibilidade de horários e acompanhamento de professores.

*   **Linguagem & Framework:** Python 3.12, Django 5.2.6.
*   **Front-end:** HTML5, CSS Vanilla (variáveis globais, Glassmorphism, UI Premium), JavaScript Vanilla e Bootstrap 5.3.3. **NÃO utilize TailwindCSS** a menos que expressamente solicitado.
*   **Banco de Dados:** SQLite3 (desenvolvimento local) e MySQL (produção no PythonAnywhere).
*   **Controle de Versão:** Git (GitHub).
*   **Deploy:** PythonAnywhere.

---

## 2. Módulos Principais (`cadastros`)

O sistema está concentrado no app `cadastros` e possui as seguintes vertentes principais:

### 2.1. CRM e Gestão de Leads
*   **Modelos:** `Lead`, `HorarioDisponivelLead`.
*   **Funcionalidades:**
    *   Pipeline de Vendas estilo Kanban (arrastar e soltar).
    *   Integração Oficial com WhatsApp (Meta API) via tela de "Caixa de Entrada" no portal.
    *   Respostas Rápidas (Templates) baseadas no Status do Lead.
    *   Coleta pública de disponibilidade: Link gerado via `UUID` (`token_disponibilidade`) enviado por WhatsApp para o Lead preencher a agenda.

### 2.2. Gestão Pedagógica (Alunos e Professores)
*   **Modelos:** `Aluno`, `Professor`, `AcompanhamentoPedagogico`.
*   **Funcionalidades:**
    *   Dashboard analítico com alertas de métricas.
    *   **Sistema de Rodízio (+2m):** Sistema inteligente que filtra alunos que não receberam acompanhamento pedagógico ("realizado") nos últimos 60 dias. **Atenção:** Essa lógica usa `Subquery` e `OuterRef` do Django no arquivo `views.py` para evitar queries N+1. Mantenha esse padrão para manter a performance.
    *   Histórico e edição de acompanhamentos com validação client-side via JavaScript.
    *   Alunos "Trancados" também possuem `token_disponibilidade` para informar quando podem retornar.

### 2.3. Match de Horários (Inteligência de Turmas)
*   **Funcionalidade:** Cruza os dados de disponibilidade (`HorarioDisponivelLead` e `HorarioDisponivelAluno`) para sugerir a criação de novas turmas agrupando pessoas com horários em comum (Heatmap).

---

## 3. Padrões de Desenvolvimento Obrigatórios

Para manter a estabilidade do portal em produção (PythonAnywhere), siga as seguintes regras rígidas ao programar:

### Segurança e Variáveis de Ambiente
*   **Nunca** deixe senhas ou tokens expostos em `settings.py` ou qualquer arquivo versionado.
*   Utilize a biblioteca `python-decouple` (`config`) para carregar credenciais do arquivo `.env` (ex: banco de dados, `EMAIL_HOST_PASSWORD`, tokens do Meta).

### Performance no Banco de Dados (ORM do Django)
*   Sempre utilize `select_related()` e `prefetch_related()` em consultas que envolvem ForeignKey.
*   Ao fazer listagens condicionais complexas (como o Rodízio de Alunos), utilize `Exists` e `Subquery` ao invés de loops `for` no Python, para evitar sobrecarga no banco em produção.

### Frontend e Design
*   **Estética:** A interface atual usa um design "Premium" moderno (Mobile-First, bordas arredondadas, glassmorphism, gradientes sutis, fontes Inter/Poppins). Qualquer tela nova deve seguir este padrão.
*   **Injeção de Dados em JS:** É proibido iterar objetos Django (`{% for %}`) diretamente dentro da tag `<script>`. Sempre serialize os dados em JSON utilizando a tag `|json_script:"id"` no HTML e faça o parse via `JSON.parse(document.getElementById('id').textContent)`.

### Migrações de Banco de Dados
*   Ao adicionar novos campos (especialmente UUIDs ou campos `unique`), cuidado ao aplicar em bancos que já possuem dados. Utilize `RunPython` para popular os dados retroativamente antes de forçar chaves únicas (veja o histórico da migração `0026`).

### Fluxo Git (Regras de Versionamento)
*   **Proibido commit direto na `main`.**
*   Crie branches `feature/nome-da-feature` para melhorias ou `hotfix/nome-do-erro` para bugs em produção.
*   Somente faça o merge para a branch principal após o desenvolvimento ser validado.

---

## 4. Comandos Essenciais

**Para rodar localmente:**
```bash
python manage.py runserver
```

**Antes de cada Deploy no Servidor:**
Lembre-se de avisar o usuário que ele precisará executar os seguintes passos no console do PythonAnywhere:
1. `git pull origin main`
2. `python manage.py migrate` (Se houver alterações em `models.py`)
3. `python manage.py collectstatic` (Para atualizar o CSS/JS na pasta `staticfiles`)
4. Recarregar o App Web no painel do PythonAnywhere.
