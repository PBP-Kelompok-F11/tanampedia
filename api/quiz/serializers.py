from rest_framework import serializers

from quiz.models import Question
from quiz.services import result_question


class AnswerOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    position = serializers.IntegerField()
    text = serializers.CharField()


class QuizQuestionSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    prompt = serializers.CharField()
    options = AnswerOptionSerializer(many=True)


class QuizResultOptionSerializer(AnswerOptionSerializer):
    is_correct = serializers.BooleanField()


class QuizResultSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    prompt = serializers.CharField()
    explanation = serializers.CharField()
    options = QuizResultOptionSerializer(many=True)
    selected_option = serializers.IntegerField(allow_null=True)
    is_correct = serializers.BooleanField()
    points_awarded = serializers.IntegerField()


class QuizStatusSerializer(serializers.Serializer):
    answered = serializers.BooleanField()
    answered_correctly = serializers.BooleanField()
    next_reset = serializers.DateField()
    reward_points = serializers.IntegerField()


class QuizTodaySerializer(serializers.Serializer):
    status = QuizStatusSerializer()
    question = QuizQuestionSerializer(allow_null=True)
    answer_token = serializers.CharField(allow_null=True)
    result = QuizResultSerializer(allow_null=True)


class QuizAnswerSerializer(serializers.Serializer):
    answer_token = serializers.CharField()
    option = serializers.IntegerField()

    def validate_option(self, value):
        if value <= 0:
            raise serializers.ValidationError('Pilihan jawaban tidak valid.')
        return value


class QuizAnswerResponseSerializer(serializers.Serializer):
    result = QuizResultSerializer()
    reward_received = serializers.BooleanField()
    next_reset = serializers.DateField()


def question_payload(question):
    return QuizQuestionSerializer({
        'question_id': question.pk, 'prompt': question.prompt,
        'options': [
            {'id': option.pk, 'position': option.position, 'text': option.text}
            for option in question.options.all()
        ],
    }).data


def result_payload(attempt):
    question = result_question(attempt)
    snapshot = attempt.question_snapshot
    options = []
    selected = None
    for option in question.options:
        if option.pk == attempt.selected_option_id:
            selected = option.pk
        options.append({
            'id': option.pk, 'position': option.position, 'text': option.text,
            'is_correct': option.position == snapshot.get('correct_position'),
        })
    return {
        'question_id': question.pk,
        'prompt': question.prompt,
        'explanation': question.explanation,
        'options': options,
        'selected_option': selected,
        'is_correct': attempt.is_correct,
        'points_awarded': attempt.points_awarded,
    }
