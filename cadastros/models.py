# cadastros/models.py
from django.db import models
from django.contrib.auth.models import User # Vamos precisar do User para os Professores
from dateutil.relativedelta import relativedelta 
from datetime import date

# Aluno permanece quase o mesmo
class Aluno(models.Model):
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