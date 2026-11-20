from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Question, Answer
from .forms import QuestionForms, AnswerForms

User = get_user_model()


class ForumModelTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="petani1", password="password123")
        self.user2 = User.objects.create_user(username="petani2", password="password123")
        self.question = Question.objects.create(
            author=self.user1,
            title="Cara menanam selada hidroponik?",
            content="Bagaimana nutrisi AB mix yang tepat untuk selada?"
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.user2,
            content="Gunakan PPM sekitar 800 hingga 1000."
        )

    def test_question_str(self):
        self.assertEqual(str(self.question), "Cara menanam selada hidroponik?")

    def test_answer_str_and_upvotes(self):
        self.assertEqual(
            str(self.answer),
            f"Answer by {self.user2} on 'Cara menanam selada hidroponik?'"
        )
        self.assertEqual(self.answer.total_upvotes, 0)
        self.answer.upvotes.add(self.user1)
        self.assertEqual(self.answer.total_upvotes, 1)


class ForumFormTests(TestCase):
    def test_question_form_valid(self):
        form = QuestionForms(data={
            "title": "Daun tomat keriting",
            "content": "Tanaman tomat saya daunnya keriting sejak kemarin."
        })
        self.assertTrue(form.is_valid())

    def test_question_form_invalid_empty(self):
        form = QuestionForms(data={"title": "", "content": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("content", form.errors)

    def test_answer_form_valid_and_invalid(self):
        valid_form = AnswerForms(data={"content": "Semprot dengan pestisida nabati."})
        self.assertTrue(valid_form.is_valid())

        invalid_form = AnswerForms(data={"content": ""})
        self.assertFalse(invalid_form.is_valid())


class ForumViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username="author_user", password="password123")
        self.user2 = User.objects.create_user(username="other_user", password="password123")

        self.question = Question.objects.create(
            author=self.user1,
            title="Mengapa daun cabai menguning?",
            content="Daun cabai rawit saya menguning di bagian bawah."
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.user2,
            content="Kemungkinan kekurangan unsur hara nitrogen."
        )
        self.ajax_headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def test_forum_home_and_search(self):
        response = self.client.get(reverse("forum:forum_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mengapa daun cabai menguning?")

        search_match = self.client.get(reverse("forum:forum_home"), {"title": "cabai"})
        self.assertEqual(len(search_match.context["questions"]), 1)

        search_miss = self.client.get(reverse("forum:forum_home"), {"title": "anggur"})
        self.assertEqual(len(search_miss.context["questions"]), 0)

    def test_question_detail_get(self):
        response = self.client.get(reverse("forum:question_detail", args=[self.question.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.question.title)
        self.assertContains(response, self.answer.content)

    def test_question_detail_post_answer_unauthenticated(self):
        url = reverse("forum:question_detail", args=[self.question.pk])
        response = self.client.post(url, {"content": "Jawaban tanpa login"})
        self.assertEqual(response.status_code, 302)

        ajax_res = self.client.post(url, {"content": "Jawaban AJAX"}, **self.ajax_headers)
        self.assertEqual(ajax_res.status_code, 401)

    def test_question_detail_post_answer_authenticated_and_ajax(self):
        self.client.login(username="user1_login", password="password123")
        self.client.force_login(self.user1)
        url = reverse("forum:question_detail", args=[self.question.pk])

        response = self.client.post(url, {"content": "Terima kasih atas sarannya!"})
        self.assertRedirects(response, url)
        self.assertEqual(self.question.answers.count(), 2)

        ajax_res = self.client.post(
            url,
            {"content": "Komentar tambahan via AJAX"},
            **self.ajax_headers
        )
        self.assertEqual(ajax_res.status_code, 201)
        self.assertEqual(ajax_res.json()["status"], "success")
        self.assertEqual(ajax_res.json()["total_answers"], 3)

        ajax_invalid = self.client.post(url, {"content": ""}, **self.ajax_headers)
        self.assertEqual(ajax_invalid.status_code, 400)

    def test_create_question_standard_and_ajax(self):
        url = reverse("forum:create_question")
        self.client.force_login(self.user1)

        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post(url, {
            "title": "Pertanyaan Baru Standar",
            "content": "Isi pertanyaan baru standar."
        })
        self.assertEqual(post_res.status_code, 302)
        self.assertTrue(Question.objects.filter(title="Pertanyaan Baru Standar").exists())

        ajax_res = self.client.post(
            url,
            {"title": "Pertanyaan Baru AJAX", "content": "Isi pertanyaan via AJAX."},
            **self.ajax_headers
        )
        self.assertEqual(ajax_res.status_code, 201)
        self.assertEqual(ajax_res.json()["question"]["title"], "Pertanyaan Baru AJAX")

        ajax_invalid = self.client.post(url, {"title": "", "content": ""}, **self.ajax_headers)
        self.assertEqual(ajax_invalid.status_code, 400)

    def test_edit_question_authorization_and_execution(self):
        url = reverse("forum:edit_question", args=[self.question.pk])

        self.client.force_login(self.user2)
        forbidden_get = self.client.get(url)
        self.assertEqual(forbidden_get.status_code, 403)

        forbidden_ajax = self.client.post(
            url,
            {"title": "Hack", "content": "Hack"},
            **self.ajax_headers
        )
        self.assertEqual(forbidden_ajax.status_code, 403)

        self.client.force_login(self.user1)
        owner_get = self.client.get(url)
        self.assertEqual(owner_get.status_code, 200)

        owner_post = self.client.post(url, {
            "title": "Judul Telah Diedit",
            "content": "Isi telah diperbarui."
        })
        self.assertRedirects(owner_post, reverse("forum:question_detail", args=[self.question.pk]))
        self.question.refresh_from_db()
        self.assertEqual(self.question.title, "Judul Telah Diedit")

        ajax_edit = self.client.post(
            url,
            {"title": "Judul Edit AJAX", "content": "Isi Edit AJAX"},
            **self.ajax_headers
        )
        self.assertEqual(ajax_edit.status_code, 200)
        self.assertEqual(ajax_edit.json()["title"], "Judul Edit AJAX")

        ajax_invalid = self.client.post(url, {"title": "", "content": ""}, **self.ajax_headers)
        self.assertEqual(ajax_invalid.status_code, 400)

    def test_delete_question_authorization_and_execution(self):
        url = reverse("forum:delete_question", args=[self.question.pk])

        self.client.force_login(self.user2)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.post(url, **self.ajax_headers).status_code, 403)

        self.client.force_login(self.user1)
        res = self.client.post(url, **self.ajax_headers)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

        q2 = Question.objects.create(author=self.user1, title="Q2", content="C2")
        res2 = self.client.post(reverse("forum:delete_question", args=[q2.pk]))
        self.assertRedirects(res2, reverse("forum:forum_home"))

    def test_delete_answer_authorization_and_execution(self):
        url = reverse("forum:delete_answer", args=[self.answer.pk])

        self.client.force_login(self.user1)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.post(url, **self.ajax_headers).status_code, 403)

        self.client.force_login(self.user2)
        res = self.client.post(url, **self.ajax_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total_answers"], 0)
        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())

        a2 = Answer.objects.create(question=self.question, author=self.user2, content="A2")
        res2 = self.client.post(reverse("forum:delete_answer", args=[a2.pk]))
        self.assertRedirects(res2, reverse("forum:question_detail", args=[self.question.pk]))

    def test_upvote_answer_toggle_and_self_upvote_protection(self):
        url = reverse("forum:upvote_answer", args=[self.answer.pk])

        self.client.force_login(self.user2)
        self_vote_std = self.client.post(url)
        self.assertRedirects(self_vote_std, reverse("forum:question_detail", args=[self.question.pk]))
        self_vote_ajax = self.client.post(url, **self.ajax_headers)
        self.assertEqual(self_vote_ajax.status_code, 400)

        self.client.force_login(self.user1)
        upvote_on = self.client.post(url, **self.ajax_headers)
        self.assertEqual(upvote_on.status_code, 200)
        self.assertTrue(upvote_on.json()["is_upvoted"])
        self.assertEqual(upvote_on.json()["total_upvotes"], 1)

        upvote_off = self.client.post(url, **self.ajax_headers)
        self.assertEqual(upvote_off.status_code, 200)
        self.assertFalse(upvote_off.json()["is_upvoted"])
        self.assertEqual(upvote_off.json()["total_upvotes"], 0)

        std_toggle = self.client.post(url)
        self.assertRedirects(std_toggle, reverse("forum:question_detail", args=[self.question.pk]))
        self.assertEqual(self.answer.total_upvotes, 1)