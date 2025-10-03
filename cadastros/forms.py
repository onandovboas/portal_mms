from django import forms
from .models import Aluno
import re

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
