"""Travel Content model tests."""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.travel_content.models import TravelReel, CuratedTrip
from apps.destinations.models import Country, Destination


class TravelReelModelTests(TestCase):
    """TravelReel model validation tests."""

    def setUp(self):
        """Set up test data."""
        self.country = Country.objects.create(name='Uzbekistan', code='UZ')
        self.destination = Destination.objects.create(
            country=self.country,
            name='Samarkand',
            category='city'
        )

    def test_video_type_requires_video_file(self):
        """Test that media_type='video' requires video_file."""
        reel = TravelReel(
            title='Test Reel',
            media_type='video',
            destination=self.destination,
            cover_image=SimpleUploadedFile(
                'test.jpg', b'fake image data', content_type='image/jpeg'
            )
        )
        with self.assertRaises(ValidationError):
            reel.full_clean()

    def test_image_type_rejects_video_file(self):
        """Test that media_type='image' rejects video_file."""
        reel = TravelReel(
            title='Test Reel',
            media_type='image',
            destination=self.destination,
            cover_image=SimpleUploadedFile(
                'test.jpg', b'fake image data', content_type='image/jpeg'
            ),
            video_file=SimpleUploadedFile(
                'test.mp4', b'fake video data', content_type='video/mp4'
            )
        )
        with self.assertRaises(ValidationError):
            reel.full_clean()


class CuratedTripModelTests(TestCase):
    """CuratedTrip model validation tests."""

    def setUp(self):
        """Set up test data."""
        self.country = Country.objects.create(name='Uzbekistan', code='UZ')
        self.destination = Destination.objects.create(
            country=self.country,
            name='Samarkand',
            category='city'
        )

    def test_duration_max_less_than_min_raises_error(self):
        """Test that duration_days_max < duration_days_min raises ValidationError."""
        trip = CuratedTrip(
            title='Test Trip',
            destination=self.destination,
            duration_days_min=6,
            duration_days_max=4,
            price_from=1000,
            cover_image=SimpleUploadedFile(
                'test.jpg', b'fake image data', content_type='image/jpeg'
            ),
            video_file=SimpleUploadedFile(
                'test.mp4', b'fake video data', content_type='video/mp4'
            )
        )
        with self.assertRaises(ValidationError):
            trip.full_clean()

    def test_group_size_max_less_than_min_raises_error(self):
        """Test that group_size_max < group_size_min raises ValidationError."""
        trip = CuratedTrip(
            title='Test Trip',
            destination=self.destination,
            duration_days_min=4,
            duration_days_max=6,
            group_size_min=5,
            group_size_max=2,
            price_from=1000,
            cover_image=SimpleUploadedFile(
                'test.jpg', b'fake image data', content_type='image/jpeg'
            ),
            video_file=SimpleUploadedFile(
                'test.mp4', b'fake video data', content_type='video/mp4'
            )
        )
        with self.assertRaises(ValidationError):
            trip.full_clean()
