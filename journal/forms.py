from django import forms

from .models import JournalEntry, PlantJournal

class PlantJournalForm(forms.ModelForm):
    class Meta:
        model = PlantJournal
        fields = ('plant_name', 'description', 'thumbnail', 'growing_medium', 'location', 'status', 'is_public')
        widgets = {
            'plant_name': forms.TextInput(attrs={
                'placeholder': 'Contoh: Cabai rawit',
                'maxlength': 200,
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Ceritakan tentang jurnal tanaman ini...',
                'rows': 3,
            }),
            'status': forms.Select(),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-slate-300 text-green-700 focus:ring-green-600',
            }),
        }

class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ('header', 'content', 'plant_condition', 'image')
        widgets = {
            'header': forms.TextInput(attrs={
                'placeholder': 'Contoh: Daun baru mulai tumbuh',
                'maxlength': 200,
            }),
            'content': forms.Textarea(attrs={
                'placeholder': 'Ceritakan perkembangan tanamanmu...',
                'rows': 4,
            }),
            'plant_condition': forms.Select(),
            'image': forms.URLInput(attrs={
                'placeholder': 'https://example.com/foto-tanaman.jpg',
                'inputmode': 'url',
            }),
        }
