from django import forms
from .models import Question, Answer

class QuestionForms(forms.ModelForm):
    class meta:
        model = Question
        fields = ['title', 'content']
        labels = {
            'title': 'Judul Pertanyaan',
            'content': 'Isi Pertanyaan',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Contoh: Mengapa daun selada hidroponik saya menguning?',
                'maxlength': 255,
            }),
            'content': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Contoh: Selama beberapa hari, saya melihat daun selada saya semakin kuning. Saya sudah...'
            }),
        }

class AnswerForms(forms.ModelForm):
    class meta:
        model = Answer
        fiels = ['content']
        labels = {'content': 'Jawaban anda'}
        widget = {'content': forms.Textarea(attrs={
            'placeholder': 'Contoh: Penguningan daun biasanya terjadi karena...',
            'rows': 5,})}
        