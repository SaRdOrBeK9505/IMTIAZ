from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.music.models import BackgroundMusic


class PublicActiveMusicTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_no_active_track_returns_404(self):
        response = self.client.get('/api/music/active/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_active_track_returned_without_auth(self):
        track = BackgroundMusic.objects.create(
            title='Lounge',
            audio_file=SimpleUploadedFile('lounge.mp3', b'fake audio', content_type='audio/mpeg'),
        )
        track.activate()

        response = self.client.get('/api/music/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Lounge')
        self.assertNotIn('file_size', response.data)  # admin-only maydon chiqmasligi kerak

    def test_only_active_track_shown(self):
        t1 = BackgroundMusic.objects.create(
            title='A', audio_file=SimpleUploadedFile('a.mp3', b'x', content_type='audio/mpeg'),
        )
        t2 = BackgroundMusic.objects.create(
            title='B', audio_file=SimpleUploadedFile('b.mp3', b'y', content_type='audio/mpeg'),
        )
        t1.activate()
        t2.activate()  # avtomatik t1 ni deaktiv qiladi (model.activate() logikasi)

        response = self.client.get('/api/music/active/')
        self.assertEqual(response.data['title'], 'B')
