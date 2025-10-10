import re
from django import forms
from .models import Aluno, Pagamento, Turma, Contrato, RegistroAula, Inscricao, Lead, AcompanhamentoPedagogico, ProvaTemplate
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
            "nome_completo", "cpf", "email", "telefone",
            "logradouro", "cidade", "estado", "status",
        ]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class":"form-control", "placeholder":"Nome completo"}),
            "cpf": forms.TextInput(attrs={"class":"form-control", "placeholder":"000.000.000-00", "maxlength":"14"}),
            "email": forms.EmailInput(attrs={"class":"form-control", "placeholder":"email@exemplo.com"}),
            "telefone": forms.TextInput(attrs={"class":"form-control", "placeholder":"(00) 00000-0000"}),
            "logradouro": forms.TextInput(attrs={"class":"form-control", "placeholder":"Rua, número"}),
            "cidade": forms.TextInput(attrs={"class":"form-control", "placeholder":"Cidade"}),
            "estado": forms.Select(attrs={"class":"form-select"}),
            "status": forms.Select(attrs={"class":"form-select"}),
        }

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf") or ""
        # normaliza para 11 dígitos; se quiser, pode manter pontuado
        digits = re.sub(r"\D", "", cpf)
        if digits and len(digits) != 11:
            raise forms.ValidationError("CPF deve ter 11 dígitos.")
        # re-formata: 000.000.000-00
        if digits:
            cpf = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return cpf

    def clean_estado(self):
        uf = (self.cleaned_data.get("estado") or "").upper()
        return uf if uf in dict(UF_CHOICES) else ""

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
    class Meta:
        model = RegistroAula
        # 1. Adicionado 'data_aula' à lista de campos
        fields = ['data_aula', 'last_parag', 'last_word', 'new_dictation', 'old_dictation', 'new_reading', 'old_reading', 'lesson_check']
        
        # 2. Adicionado o widget para o novo campo
        widgets = {
            'data_aula': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_parag': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_word': forms.TextInput(attrs={'class': 'form-control'}),
            'new_dictation': forms.NumberInput(attrs={'class': 'form-control'}),
            'old_dictation': forms.NumberInput(attrs={'class': 'form-control'}),
            'new_reading': forms.NumberInput(attrs={'class': 'form-control'}),
            'old_reading': forms.NumberInput(attrs={'class': 'form-control'}),
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
            'pontos_fortes', 'pontos_melhorar', 'estrategia', 'comentarios_extras'
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