from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AnswerOption, Question


INPUT_CLASSES = (
    'block w-full rounded-xl border border-primary-900 bg-raised px-4 py-3 '
    'text-primary-900 placeholder:text-grey-500 hover:bg-primary-50 '
    'focus:bg-raised disabled:cursor-not-allowed disabled:bg-grey-100'
)


class QuestionForm(forms.ModelForm):
    option_1 = forms.CharField(label='Pilihan A', max_length=500)
    option_2 = forms.CharField(label='Pilihan B', max_length=500)
    option_3 = forms.CharField(label='Pilihan C', max_length=500)
    option_4 = forms.CharField(label='Pilihan D', max_length=500)
    correct_position = forms.TypedChoiceField(
        label='Jawaban yang benar', coerce=int,
        choices=[(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')],
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Question
        fields = [
            'prompt', 'option_1', 'option_2', 'option_3', 'option_4',
            'correct_position', 'explanation', 'is_active',
        ]
        labels = {
            'prompt': 'Pertanyaan',
            'explanation': 'Penjelasan jawaban',
            'is_active': 'Soal aktif',
        }
        help_texts = {
            'explanation': 'Penjelasan ini ditampilkan setelah pengguna menjawab.',
            'is_active': 'Hanya soal aktif yang masuk ke pemilihan acak.',
        }
        widgets = {
            'prompt': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tulis pertanyaan kuis'}),
            'explanation': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tulis penjelasan jawaban'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for option in self.instance.options.all():
                self.initial[f'option_{option.position}'] = option.text
                if option.is_correct:
                    self.initial['correct_position'] = option.position
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'size-5 shrink-0 accent-primary-600'
            else:
                field.widget.attrs['class'] = INPUT_CLASSES
                if isinstance(field.widget, forms.Textarea):
                    field.widget.attrs['class'] += ' resize-y'

    def clean(self):
        cleaned = super().clean()
        options = [cleaned.get(f'option_{position}', '').casefold() for position in range(1, 5)]
        if all(options) and len(set(options)) != 4:
            raise ValidationError('Keempat pilihan jawaban harus berbeda.')
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError('QuestionForm harus disimpan bersama pilihan jawabannya.')
        if self.instance.pk:
            current = Question.objects.select_for_update().filter(pk=self.instance.pk).first()
            if current is None:
                raise ValidationError('Soal sudah dihapus. Kembali ke daftar soal untuk melanjutkan.')
        question = super().save()
        question.options.update(is_correct=False)
        for position in range(1, 5):
            AnswerOption.objects.update_or_create(
                question=question, position=position,
                defaults={
                    'text': self.cleaned_data[f'option_{position}'],
                    'is_correct': self.cleaned_data['correct_position'] == position,
                },
            )
        question.validate_options()
        return question
