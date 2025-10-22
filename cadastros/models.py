# cadastros/models.py
from django.db import models
from django.contrib.auth.models import User # Vamos precisar do User para os Professores
from dateutil.relativedelta import relativedelta 
from datetime import date, timezone, timedelta
from django.utils import timezone
import uuid

# Aluno permanece quase o mesmo
class Aluno(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="perfil_aluno")
    STATUS_CHOICES = [("ativo", "Ativo"), ("inativo", "Inativo"), ("trancado", "Trancado")]
    nome_completo = models.CharField(max_length=200)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    logradouro = models.CharField("Endereço", max_length=255, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    data_matricula = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ativo")
    

    def __str__(self):
        return self.nome_completo

# Professor agora se liga ao sistema de Usuários do Django
class Professor(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    nome_completo = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    def __str__(self):
        return self.nome_completo

# Turma foi atualizada com Stage e Anotações
class Turma(models.Model):
    nome = models.CharField("Nome da Turma", max_length=100)
    stage = models.IntegerField("Estágio", default=1)
    anotacoes_gerais = models.TextField("Anotações dos Professores", blank=True, null=True)
    # A relação com Aluno agora é feita através do modelo 'Inscricao'
    # Remova a linha 'alunos = models.ManyToManyField(Aluno, blank=True)'
    def __str__(self):
        return f"{self.nome} (Stage {self.stage})"

# NOVO MODELO 'PONTE': A Inscrição
class Inscricao(models.Model):
    STATUS_CHOICES = [
        ('matriculado', 'Matriculado'),
        ('acompanhando', 'Acompanhando'),
        ('experimental', 'Experimental'),
        ('trancado', 'Trancado'),
        ('desistiu', 'Desistiu'),
    ]
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='matriculado')
    
    def __str__(self):
        return f"{self.aluno.nome_completo} em {self.turma.nome} ({self.status})"

# NOVO MODELO: O Registro de cada aula
class RegistroAula(models.Model):
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE)
    data_aula = models.DateField()
    professor = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True)
    last_parag = models.IntegerField("Último Parágrafo", null=True, blank=True)
    last_word = models.CharField("Última Palavra", max_length=100, null=True, blank=True)
    new_dictation = models.IntegerField("Ditado Novo (Nº)", null=True, blank=True)
    old_dictation = models.IntegerField("Ditado Antigo (Nº)", null=True, blank=True)
    new_reading = models.IntegerField("Leitura Nova (Nº)", null=True, blank=True)
    old_reading = models.IntegerField("Leitura Antiga (Nº)", null=True, blank=True)
    lesson_check = models.CharField("Lesson Check", max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Registro de {self.turma.nome} em {self.data_aula.strftime('%d/%m/%Y')}"

# NOVO MODELO: O controle de presença de cada aluno em cada aula
class Presenca(models.Model):
    registro_aula = models.ForeignKey(RegistroAula, on_delete=models.CASCADE)
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    presente = models.BooleanField(default=False)

    def __str__(self):
        status = "Presente" if self.presente else "Falta"
        return f"{self.aluno.nome_completo} - {status} em {self.registro_aula.data_aula.strftime('%d/%m/%Y')}"
    
PLANO_CHOICES = [
    ('anual', 'Anual'),
    ('semestral', 'Semestral'),
    ('flex', 'Mensal Flexível'),
]
class Contrato(models.Model):
    # ... (código anterior da classe) ...
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="contratos")
    plano = models.CharField(max_length=10, choices=PLANO_CHOICES)
    data_inicio = models.DateField()
    # 👇 Tornamos o campo verdadeiramente opcional, permitindo valores nulos no banco de dados
    data_fim = models.DateField(null=True, blank=True) 
    valor_mensalidade = models.DecimalField(max_digits=7, decimal_places=2)
    valor_matricula = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    parcelas_matricula = models.IntegerField(default=1)
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # A lógica agora só se aplica a planos com duração definida.
        if self.plano == 'anual':
            self.data_fim = self.data_inicio + relativedelta(years=1)
        elif self.plano == 'semestral':
            self.data_fim = self.data_inicio + relativedelta(months=6)
        # Se for 'flex', a data_fim permanecerá nula (em aberto).
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Contrato {self.get_plano_display()} de {self.aluno.nome_completo}"
    
    @property
    def valor_total_contrato(self):
        if self.plano == 'anual':
            return self.valor_mensalidade * 12
        elif self.plano == 'semestral':
            return self.valor_mensalidade * 6
        return self.valor_mensalidade # Para planos flexíveis, o total é apenas uma mensalidade


class Pagamento(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
        ('parcial', 'Parcialmente Pago'),
        ('atrasado', 'Atrasado'),
        ('cancelado', 'Cancelado'),
    ]
    TIPO_CHOICES = [
        ('mensalidade', 'Mensalidade'),
        ('matricula', 'Matrícula'),
        ('material', 'Material Didático'),
        ('outro', 'Outro'),
    ]

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="pagamentos")
    contrato = models.ForeignKey(Contrato, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField("Tipo de Pagamento", max_length=15, choices=TIPO_CHOICES, default='mensalidade')
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=7, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')
    mes_referencia = models.DateField("Mês de Referência")
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)
    valor_pago = models.DecimalField("Valor Pago", max_digits=7, decimal_places=2, default=0)

    @property
    def valor_restante(self):
        return self.valor - self.valor_pago

    def __str__(self):
        return f"{self.descricao} - {self.aluno.nome_completo} ({self.get_status_display()})"
    
class AcompanhamentoFalta(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('resolvido', 'Resolvido'),
    ]
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="acompanhamentos")
    data_inicio_sequencia = models.DateField("Início da Sequência de Faltas")
    numero_de_faltas = models.IntegerField(default=3)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')
    motivo = models.TextField("Motivo das Faltas e Ações Tomadas", blank=True, null=True)
    data_resolucao = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Acompanhamento de {self.aluno.nome_completo} - {self.get_status_display()}"
    
class AcompanhamentoPedagogico(models.Model):
    STATUS_CHOICES = [
        ('agendado', 'Agendado'),
        ('realizado', 'Realizado'),
        ('cancelado', 'Cancelado'),
    ]

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="acompanhamentos_pedagogicos")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='agendado')
    
    # Datas
    data_agendamento = models.DateTimeField("Data e Hora do Agendamento")
    data_realizacao = models.DateTimeField("Data e Hora de Realização", null=True, blank=True)
    
    # Contexto no momento do acompanhamento
    stage_no_momento = models.IntegerField("Stage do Aluno no Momento do Acompanhamento")
    
    # Campos da Entrevista
    dificuldades = models.TextField(blank=True)
    relacao_lingua = models.TextField("Relação com a língua", blank=True)
    objetivo_estudo = models.TextField("Objetivo do estudo", blank=True)
    correcao_ditados = models.TextField("Correção de ditados", blank=True)
    pontos_fortes = models.TextField(blank=True)
    pontos_melhorar = models.TextField("Pontos a serem melhorados", blank=True)
    estrategia = models.TextField("Estratégia", blank=True)
    comentarios_extras = models.TextField(blank=True)
    atividades_recomendadas = models.TextField("Atividades e Recomendações", blank=True, null=True)

    # Rastreabilidade
    criado_por = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True, related_name="acompanhamentos_criados")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_agendamento']

    def __str__(self):
        return f"Acompanhamento de {self.aluno.nome_completo} em {self.data_agendamento.strftime('%d/%m/%Y')}"
    

class TesteStage(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="testes_stage")
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE)
    data_teste = models.DateField(default=timezone.now)
    stage_atingido = models.IntegerField("Stage Atingido")
    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-data_teste', '-criado_em']
    
    def __str__(self):
        return f"Teste Stage {self.stage_atingido} - {self.aluno.nome_completo}"

class HorarioAula(models.Model):
    DIA_CHOICES = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.IntegerField("Dia da semana", choices=DIA_CHOICES)
    horario_inicio = models.TimeField("Horário de Início")
    horario_fim = models.TimeField("Horário de Fim", null=True, blank=True)

    class Meta:
        ordering = ['dia_semana', 'horario_inicio'] # Ordena os horários

    def __str__(self):
        return f"{self.turma.nome} - {self.get_dia_semana_display()} às {self.horario_inicio.strftime('%H:%M')}"
    
class Lead(models.Model):
    STATUS_CHOICES = [
        ('novo', 'Novo Contato'),
        ('contatado', 'Contato Realizado'),
        ('agendado', 'Aula Experimental Agendada'),
        ('congelado', 'Congelado'),
        ('convertido', 'Convertido em Aluno'),
        ('perdido', 'Perdido'),
    ]
    
    FONTE_CHOICES = [
        ('indicacao', 'Indicação'),
        ('instagram', 'Instagram'),
        ('google', 'Google'),
        ('fachada', 'Fachada da Escola'),
        ('outro', 'Outro'),
    ]

    nome_completo = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='novo')
    fonte_contato = models.CharField("Origem do Contato", max_length=15, choices=FONTE_CHOICES, blank=True)
    disponibilidade_horarios = models.TextField("Disponibilidade de Horários", blank=True)
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.nome_completo} ({self.get_status_display()})"
    
class TokenAtualizacaoAluno(models.Model):
    """
    Armazena um token seguro e de uso único para um aluno atualizar seus dados.
    """
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="tokens_atualizacao")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    def __str__(self):
        return f"Token para {self.aluno.nome_completo} criado em {self.criado_em.strftime('%d/%m/%Y %H:%M')}"

    @property
    def is_expired(self):
        """Verifica se o token expirou (válido por 24 horas)."""
        return self.criado_em + timedelta(hours=24) < timezone.now()
    
class ProvaTemplate(models.Model):
    """
    O "gabarito" ou molde de uma prova, associado a um Stage.
    """
    titulo = models.CharField("Título da Prova", max_length=200)
    stage_referencia = models.IntegerField("Stage de Referência")
    instrucoes = models.TextField("Instruções Gerais", blank=True)
    pontos_para_aprovar = models.IntegerField("Pontos para Aprovar", null=True, blank=True)
    ordem_sessoes = models.JSONField(
        "Ordem das Secções", 
        default=list,
        help_text="Lista com a ordem dos tipos de questão. Ex: [\"dictation\", \"yes_no\"]"
    )
    # ✅ NOVO CAMPO PARA INSTRUÇÕES DAS SECÇÕES ✅
    instrucoes_sessoes = models.JSONField(
        "Instruções das Secções",
        default=dict, # Define um dicionário vazio como padrão
        blank=True,
        help_text='Dicionário com instruções por tipo de questão. Ex: {"yes_no": "Ouça e marque Sim ou Não."}'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['stage_referencia', 'titulo']
        verbose_name = "Gabarito de Prova"
        verbose_name_plural = "Gabaritos de Provas"

    def __str__(self):
        return f"Prova - Stage {self.stage_referencia}: {self.titulo}"



class Questao(models.Model):
    """
    Uma única questão dentro de um ProvaTemplate.
    """
    TIPO_QUESTAO_CHOICES = [
        ('dictation', 'Dictation'),
        ('yes_no', 'Yes/No Quiz'),
        ('multiple_choice', 'Multiple Choice (Escrito)'),
        ('error_correction', 'Error Correction'),
        ('oral_multiple_choice', 'Multiple Choice (Oral)'),
        ('gap_fill', 'Gap Fill'),
        ('dissertativa', 'Escrita / Dissertativa'), # ✅ NOVO TIPO DE QUESTÃO ✅
    ]
    prova_template = models.ForeignKey(ProvaTemplate, on_delete=models.CASCADE, related_name="questoes")
    ordem = models.PositiveIntegerField("Ordem")
    tipo_questao = models.CharField("Tipo da Questão", max_length=30, choices=TIPO_QUESTAO_CHOICES)
    enunciado = models.TextField("Enunciado/Instrução")
    pontos = models.IntegerField("Pontos", default=1)
    dados_questao = models.JSONField(null=True, blank=True, help_text="Ex: {\"opcoes\": {\"a\": \"A\", \"b\": \"B\"}, \"resposta_correta\": \"b\"}")

    class Meta:
        ordering = ['prova_template', 'ordem']
        verbose_name = "Questão"
        verbose_name_plural = "Questões"

    def __str__(self):
        return f"Q{self.ordem}: {self.get_tipo_questao_display()} ({self.prova_template.titulo})"


class AlunoProva(models.Model):
    """
    O registo de uma prova realizada por um aluno, com seus resultados.
    """
    STATUS_CHOICES = [
        ('nao_iniciada', 'Não Iniciada'),
        ('em_progresso', 'Em Progresso'),
        ('aguardando_correcao', 'Aguardando Correção'),
        ('finalizada', 'Finalizada'),
    ]
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="provas")
    prova_template = models.ForeignKey(ProvaTemplate, on_delete=models.PROTECT, verbose_name="Gabarito da Prova")
    # ✅ DEFAULT ATUALIZADO ✅
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='nao_iniciada')
    data_realizacao = models.DateField("Data de Realização", default=timezone.now)
    corrigido_por = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True, blank=True)
    nota_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    resultados = models.JSONField(null=True, blank=True)
    observacoes_gerais = models.TextField("Observações Gerais do Professor", blank=True)
    
    pontuacao_total = models.DecimalField("Pontuação Máxima da Prova", max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-data_realizacao']
        verbose_name = "Prova do Aluno"
        verbose_name_plural = "Provas dos Alunos"

    def __str__(self):
        return f"Prova de {self.aluno.nome_completo} - {self.prova_template.titulo}"
class RespostaAluno(models.Model):
    """
    Armazena a resposta de um aluno para uma única questão de uma prova.
    """
    aluno_prova = models.ForeignKey(AlunoProva, on_delete=models.CASCADE, related_name="respostas")
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE)
    
    # A resposta pode ser um texto (para ditado, gap-fill) ou uma opção (para múltipla escolha)
    resposta_texto = models.TextField("Resposta em Texto", blank=True, null=True)
    resposta_opcao = models.CharField("Opção Selecionada", max_length=10, blank=True, null=True)

    # Campos preenchidos pelo professor durante a correção
    pontos_obtidos = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback_professor = models.TextField("Feedback do Professor", blank=True, null=True)
    resposta_corrigida_html = models.TextField("Resposta Corrigida (HTML)", blank=True, null=True)
    corrigido = models.BooleanField(default=False)

    class Meta:
        # Garante que um aluno só pode ter uma resposta por questão em cada prova
        unique_together = ('aluno_prova', 'questao')
        ordering = ['questao__ordem']

    def __str__(self):
        return f"Resposta de {self.aluno_prova.aluno.nome_completo} para Q{self.questao.ordem}"
