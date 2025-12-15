import re
from django import forms
from .models import Aluno, Pagamento, Turma, Contrato, RegistroAula, Inscricao, Lead, AcompanhamentoPedagogico, ProvaTemplate, PesquisaSatisfacao
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm

UF_CHOICES = [
    ("", "—"),
    ("AC","AC"),("AL","AL"),("AP","AP"),("AM","AM"),("BA","BA"),("CE","CE"),
    ("DF","DF"),("ES","ES"),("GO","GO"),("MA","MA"),("MT","MT"),("MS","MS"),
    ("MG","MG"),("PA","PA"),("PB","PB"),("PR","PR"),("PE","PE"),("PI","PI"),
    ("RJ","RJ"),("RN","RN"),("RS","RS"),("RO","RO"),("RR","RR"),("SC","SC"),
    ("SP","SP"),("SE","SE"),("TO","TO"),
]

class AlunoForm(forms.ModelForm):
    # Se seu modelo tiver status (tem STATUS_CHOICES), o Django já monta o select.
    estado = forms.ChoiceField(choices=UF_CHOICES, required=False)

    class Meta:
        model = Aluno
        fields = [
            "nome_completo", "email", "telefone",
            "status",
        ]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class":"form-control", "placeholder":"Nome completo"}),
            "email": forms.EmailInput(attrs={"class":"form-control", "placeholder":"email@exemplo.com"}),
            "telefone": forms.TextInput(attrs={"class":"form-control", "placeholder":"(00) 00000-0000"}),
            "status": forms.Select(attrs={"class":"form-select"}),
        }

    
class PagamentoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Esta mágica acontece aqui:
        # 1. Verificamos se o formulário está editando um pagamento existente.
        # 2. Se sim, pegamos a data de vencimento.
        # 3. Formatamos a data para o padrão AAAA-MM-DD que o HTML entende.
        if self.instance and self.instance.data_vencimento:
            self.initial['data_vencimento'] = self.instance.data_vencimento.strftime('%Y-%m-%d')

    class Meta:
        model = Pagamento
        fields = ['descricao', 'valor', 'data_vencimento', 'status', 'valor_pago']
        widgets = {
            # O widget de data agora funcionará corretamente
            'data_vencimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_pago': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class AlunoExperimentalForm(forms.ModelForm):
    # Este campo busca todas as turmas cadastradas e exibe como um menu de seleção.
    turma_experimental = forms.ModelChoiceField(
        queryset=Turma.objects.all().order_by('nome'),
        label="Turma para aula experimental",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Aluno
        # Pedimos apenas os campos essenciais para um primeiro contato
        fields = ['nome_completo', 'telefone', 'email']
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class":"form-control", "placeholder":"Nome completo"}),
            "telefone": forms.TextInput(attrs={"class":"form-control", "placeholder":"(00) 00000-0000"}),
            "email": forms.EmailInput(attrs={"class":"form-control", "placeholder":"email@exemplo.com"}),
        }

class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        # O campo 'aluno' será preenchido automaticamente pela view
        fields = ['plano', 'data_inicio', 'valor_mensalidade', 'valor_matricula', 'parcelas_matricula', 'observacoes']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'plano': forms.Select(attrs={'class': 'form-select'}),
            'valor_mensalidade': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_matricula': forms.NumberInput(attrs={'class': 'form-control'}),
            'parcelas_matricula': forms.NumberInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class RegistroAulaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        """
        Pré-preenche o campo de data no formato correto que o HTML5 'date' espera.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data_aula:
            self.initial['data_aula'] = self.instance.data_aula.strftime('%Y-%m-%d')        
    class Meta:
        model = RegistroAula
        fields = ['data_aula', 'last_parag', 'last_word', 'new_dictation', 'old_dictation', 'new_reading', 'old_reading', 'lesson_check']
        
        labels = {
            'data_aula': 'Class Date',
            'last_parag': 'Last Page Number',
            'last_word': 'Last Word',
            'new_dictation': 'New Dictation',
            'old_dictation': 'Old Dictation',
            'new_reading': 'New Reading',
            'old_reading': 'Old Reading',
            'lesson_check': 'Lesson Check',
        }
        
        # --- CORREÇÃO AQUI ---
        # Trocamos NumberInput por TextInput para aceitar texto
        widgets = {
            'data_aula': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_parag': forms.NumberInput(attrs={'class': 'form-control'}), # Este continua sendo número
            'last_word': forms.TextInput(attrs={'class': 'form-control'}),
            'new_dictation': forms.TextInput(attrs={'class': 'form-control'}), # MUDADO
            'old_dictation': forms.TextInput(attrs={'class': 'form-control'}), # MUDADO
            'new_reading': forms.TextInput(attrs={'class': 'form-control'}),   # MUDADO
            'old_reading': forms.TextInput(attrs={'class': 'form-control'}),   # MUDADO
            'lesson_check': forms.TextInput(attrs={'class': 'form-control'}),
        }


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['nome_completo', 'telefone', 'email', 'status', 'fonte_contato', 'disponibilidade_horarios', 'observacoes']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'fonte_contato': forms.Select(attrs={'class': 'form-select'}),
            'disponibilidade_horarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AcompanhamentoPedagogicoForm(forms.ModelForm):
    class Meta:
        model = AcompanhamentoPedagogico
        # Campos que o utilizador irá preencher. 'aluno' e 'criado_por' são definidos na view.
        fields = [
            'status', 'data_agendamento', 'data_realizacao', 'stage_no_momento',
            'dificuldades', 'relacao_lingua', 'objetivo_estudo', 'correcao_ditados',
            'pontos_fortes', 'pontos_melhorar', 'estrategia', 'comentarios_extras',
            'atividades_recomendadas'
        ]

        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'data_agendamento': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'data_realizacao': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'stage_no_momento': forms.NumberInput(attrs={'class': 'form-control'}),
            'dificuldades': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'relacao_lingua': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'objetivo_estudo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'correcao_ditados': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pontos_fortes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pontos_melhorar': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estrategia': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comentarios_extras': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'atividades_recomendadas': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole links, descreva atividades ou faça recomendações. Essas informações aparecerão para os alunos!'}),
        }

class MyPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': ' '})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': ' '})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': ' '})

class LiberarProvaForm(forms.Form):
    """
    Formulário para o professor selecionar qual ProvaTemplate aplicar a um aluno.
    """
    prova_template = forms.ModelChoiceField(
        queryset=ProvaTemplate.objects.all().order_by('stage_referencia', 'titulo'),
        label="Selecione o Gabarito da Prova",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class PlanoAulaForm(forms.ModelForm):
    """
    Formulário específico para o PROFESSOR planejar uma aula futura.
    Não inclui campos de presença, apenas o conteúdo da aula.
    """
    class Meta:
        model = RegistroAula
        # Inclui apenas os campos relevantes para o planejamento
        fields = [
            'data_aula', 'last_parag', 'last_word', 'new_dictation', 
            'old_dictation', 'new_reading', 'old_reading', 'lesson_check'
        ]
        
        # --- ALTERAÇÕES AQUI (Removendo o "(No.)") ---
        labels = {
            'data_aula': 'Data da Aula Planejada',
            'last_parag': 'Last Page Number',
            'last_word': 'Last Word',
            'new_dictation': 'New Dictation',
            'old_dictation': 'Old Dictation',
            'new_reading': 'New Reading',
            'old_reading': 'Old Reading',
            'lesson_check': 'Lesson Check',
        }
        
        # --- ALTERAÇÕES AQUI (Mudando de NumberInput para TextInput) ---
        widgets = {
            'data_aula': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_parag': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_word': forms.TextInput(attrs={'class': 'form-control'}),
            'new_dictation': forms.TextInput(attrs={'class': 'form-control'}), # MUDADO
            'old_dictation': forms.TextInput(attrs={'class': 'form-control'}), # MUDADO
            'new_reading': forms.TextInput(attrs={'class': 'form-control'}),   # MUDADO
            'old_reading': forms.TextInput(attrs={'class': 'form-control'}),   # MUDADO
            'lesson_check': forms.TextInput(attrs={'class': 'form-control'}),
        }
# --- FIM DO FORMULÁRIO ADICIONADO ---

class PesquisaSatisfacaoForm(forms.ModelForm):
    class Meta:
        model = PesquisaSatisfacao
        fields = [
            'email_confirmado', 'telefone_atualizado', 'stage_atual_informado',
            'faixa_etaria', 'escolaridade', 
            'area_atuacao', 'cargo_atual', 'objetivo_ingles', 'como_conheceu',
            'segue_instagram', 'conteudo_desejado',
            'nps_score', 'comentarios_gerais'
        ]
        widgets = {
            'email_confirmado': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Seu melhor e-mail'}),
            'telefone_atualizado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'stage_atual_informado': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 3'}),
            
            # Selects estilizados
            'faixa_etaria': forms.Select(attrs={'class': 'form-select'}),
            'escolaridade': forms.Select(attrs={'class': 'form-select'}),
            'como_conheceu': forms.Select(attrs={'class': 'form-select'}),
            
            # Campos de Texto
            'area_atuacao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Saúde, Tecnologia, Direito...'}),
            'cargo_atual': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Estudante, Gerente, Autônomo...'}),
            'objetivo_ingles': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Intercâmbio, Trabalho, Viagem...'}),
            
            'conteudo_desejado': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'comentarios_gerais': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            
            # NPS como Radio Select para o Django entender a validação, embora o HTML seja customizado
            'nps_score': forms.RadioSelect(choices=[(i, str(i)) for i in range(11)]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Definir os OBRIGATÓRIOS (Isso impede o envio vazio)
        self.fields['email_confirmado'].required = True
        self.fields['telefone_atualizado'].required = True
        self.fields['stage_atual_informado'].required = True
        self.fields['nps_score'].required = True

        # 2. Definir os OPCIONAIS (Evita erro de validação se estiverem vazios)
        campos_opcionais = [
            'faixa_etaria', 'escolaridade', 'area_atuacao', 'cargo_atual', 
            'objetivo_ingles', 'como_conheceu', 'conteudo_desejado', 
            'comentarios_gerais', 'segue_instagram'
        ]
        for campo in campos_opcionais:
            self.fields[campo].required = False

# Formulário para recuperação de senha (usado na próxima Sprint, mas já deixamos pronto)
class EsqueciSenhaForm(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Digite seu e-mail cadastrado'})
    )

class EnviarEmailForm(forms.Form):
    DESTINATARIO_CHOICES = [
        ('todos', 'Todos os Alunos Ativos'),
        ('turma', 'Uma Turma Específica'),
        ('aluno', 'Um Aluno Específico'),
    ]
    
    tipo_destinatario = forms.ChoiceField(
        choices=DESTINATARIO_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'toggleDestinatario(this)'})
    )
    
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.all().order_by('nome'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'select_turma'})
    )
    
    aluno = forms.ModelChoiceField(
        queryset=Aluno.objects.filter(status='ativo').order_by('nome_completo'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'select_aluno'})
    )
    
    assunto = forms.CharField(
        max_length=200, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto do E-mail'})
    )
    
    mensagem = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Escreva sua mensagem aqui...'})
    )