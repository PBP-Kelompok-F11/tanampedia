import django.db.models.deletion
from django.db import migrations, models


def backfill_snapshots(apps, schema_editor):
    Attempt = apps.get_model('quiz', 'QuizAttempt')
    attempts = Attempt.objects.using(schema_editor.connection.alias).select_related(
        'selected_option__question',
    ).prefetch_related('selected_option__question__options')
    for attempt in attempts.iterator(chunk_size=500):
        selected = attempt.selected_option
        question = selected.question
        options = list(question.options.all())
        attempt.question_snapshot = {
            'question_id': question.pk,
            'prompt': question.prompt,
            'explanation': question.explanation,
            'options': [
                {'id': option.pk, 'position': option.position, 'text': option.text}
                for option in options
            ],
            'correct_position': next((option.position for option in options if option.is_correct), None),
            'selected_position': selected.position,
        }
        attempt.save(update_fields=['question_snapshot'], using=schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0002_daily_answer_rewards'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizattempt',
            name='question_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_snapshots, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='dailychallenge',
            name='question',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challenges', to='quiz.question'),
        ),
        migrations.AlterField(
            model_name='quizattempt',
            name='selected_option',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attempts', to='quiz.answeroption'),
        ),
    ]
