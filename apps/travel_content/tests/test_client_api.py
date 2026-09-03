"""Travel Content Client API tests."""

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from PIL import Image
import io

from apps.travel_content.models import TravelReel, CuratedTrip
from apps.destinations.models import Country, Destination


def create_test_image():
    """Create a valid test image using PIL."""
    img = Image.new('RGB', (100, 100), color='red')
    img_io = io.BytesIO()
    img.save(img_io, format='JPEG')
    img_io.seek(0)
    return img_io.getvalue()


class TravelContentClientAPITests(TestCase):
    """Client API tests for read-only endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.country = Country.objects.create(name='Uzbekistan', code='UZ')
        self.destination = Destination.objects.create(
            country=self.country,
            name='Samarkand',
            category='city'
        )
        
        # Create active and inactive reels
        self.active_reel = TravelReel.objects.create(
            title='Active Reel',
            media_type='image',
            destination=self.destination,
            is_active=True,
            cover_image=SimpleUploadedFile(
                'test.jpg', create_test_image(), content_type='image/jpeg'
            )
        )
        self.inactive_reel = TravelReel.objects.create(
            title='Inactive Reel',
            media_type='image',
            destination=self.destination,
            is_active=False,
            cover_image=SimpleUploadedFile(
                'test2.jpg', create_test_image(), content_type='image/jpeg'
            )
        )
        
        # Create active and inactive trips
        self.active_trip = CuratedTrip.objects.create(
            title='Active Trip',
            destination=self.destination,
            duration_days_min=4,
            duration_days_max=6,
            price_from=1000,
            is_active=True,
            cover_image=SimpleUploadedFile(
                'test.jpg', create_test_image(), content_type='image/jpeg'
            ),
            video_file=SimpleUploadedFile(
                'test.mp4', b'fake video data', content_type='video/mp4'
            )
        )
        self.inactive_trip = CuratedTrip.objects.create(
            title='Inactive Trip',
            destination=self.destination,
            duration_days_min=4,
            duration_days_max=6,
            price_from=1000,
            is_active=False,
            cover_image=SimpleUploadedFile(
                'test2.jpg', create_test_image(), content_type='image/jpeg'
            ),
            video_file=SimpleUploadedFile(
                'test2.mp4', b'fake video data', content_type='video/mp4'
            )
        )

    def test_client_list_shows_only_active_reels(self):
        """Test that client list only shows active reels."""
        response = self.client.get('/api/travel-content/reels/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.active_reel.id))

    def test_client_list_shows_only_active_trips(self):
        """Test that client list only shows active trips."""
        response = self.client.get('/api/travel-content/curated-trips/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.active_trip.id))

    def test_client_detail_increments_view_count_reel(self):
        """Test that accessing detail endpoint increments view_count for reels."""
        initial_view_count = self.active_reel.view_count
        response = self.client.get(f'/api/travel-content/reels/{self.active_reel.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.active_reel.refresh_from_db()
        self.assertEqual(self.active_reel.view_count, initial_view_count + 1)

    def test_client_detail_increments_view_count_trip(self):
        """Test that accessing detail endpoint increments view_count for trips."""
        initial_view_count = self.active_trip.view_count
        response = self.client.get(f'/api/travel-content/curated-trips/{self.active_trip.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.active_trip.refresh_from_db()
        self.assertEqual(self.active_trip.view_count, initial_view_count + 1)

    def test_client_cannot_access_inactive_reel(self):
        """Test that client cannot access inactive reel detail."""
        response = self.client.get(f'/api/travel-content/reels/{self.inactive_reel.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_cannot_access_inactive_trip(self):
        """Test that client cannot access inactive trip detail."""
        response = self.client.get(f'/api/travel-content/curated-trips/{self.inactive_trip.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_endpoints_are_public(self):
        """Test that client endpoints do not require authentication."""
        # No authentication set
        response = self.client.get('/api/travel-content/reels/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.get('/api/travel-content/curated-trips/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_like_endpoint_does_not_exist(self):
        """Test that like endpoint does not exist (removed as requested)."""
        response = self.client.post(f'/api/travel-content/reels/{self.active_reel.id}/like/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
