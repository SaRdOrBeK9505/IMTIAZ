"""Travel Content Admin API tests."""

from django.test import TestCase
from django.contrib.auth import get_user_model
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

User = get_user_model()


class TravelContentAdminAPITests(TestCase):
    """Admin API permission and CRUD tests."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            phone='+998901234567',
            password='adminpass123'
        )
        self.regular_user = User.objects.create_user(
            phone='+998901234568',
            password='userpass123'
        )
        self.country = Country.objects.create(name='Uzbekistan', code='UZ')
        self.destination = Destination.objects.create(
            country=self.country,
            name='Samarkand',
            category='city'
        )

    def test_non_admin_cannot_access_admin_endpoints(self):
        """Test that non-admin users get 403 on admin endpoints."""
        self.client.force_authenticate(user=self.regular_user)
        
        # Try to access admin reels endpoint
        response = self.client.get('/api/travel-content/admin/reels/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Try to access admin curated trips endpoint
        response = self.client.get('/api/travel-content/admin/curated-trips/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_admin_endpoints(self):
        """Test that admin users can access admin endpoints."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Access admin reels endpoint
        response = self.client.get('/api/travel-content/admin/reels/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Access admin curated trips endpoint
        response = self.client.get('/api/travel-content/admin/curated-trips/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_create_travel_reel(self):
        """Test that admin can create a TravelReel via multipart POST."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'St. Moritz',
            'subtitle': 'Zima, lыji va stil',
            'media_type': 'image',
            'destination': str(self.destination.id),
            'cover_image': SimpleUploadedFile('cover.jpg', create_test_image(), content_type='image/jpeg'),
            'is_active': True,
            'sort_order': 0,
        }
        response = self.client.post('/api/travel-content/admin/reels/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TravelReel.objects.count(), 1)
        self.assertEqual(TravelReel.objects.first().title, 'St. Moritz')

    def test_admin_cannot_create_curated_trip_without_video(self):
        """CuratedTrip video'siz yaratilmasligi kerak — asosiy biznes qoidasi."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'IMTIAZ Dubai Luxury',
            'destination': str(self.destination.id),
            'duration_days_min': 4,
            'duration_days_max': 6,
            'group_size_min': 1,
            'group_size_max': 2,
            'price_from': '3400.00',
            'currency': 'USD',
            'cover_image': SimpleUploadedFile('cover.jpg', create_test_image(), content_type='image/jpeg'),
            # video_file ATAYLAB berilmagan
        }
        response = self.client.post('/api/travel-content/admin/curated-trips/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that video_file error is in the response (in errors dict)
        self.assertIn('video_file', response.data.get('errors', {}))
        self.assertEqual(CuratedTrip.objects.count(), 0)

    def test_admin_can_create_curated_trip(self):
        """Test that admin can create a CuratedTrip when both cover_image and video_file are provided."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title': 'IMTIAZ Dubai Luxury',
            'destination': str(self.destination.id),
            'duration_days_min': 4,
            'duration_days_max': 6,
            'group_size_min': 1,
            'group_size_max': 2,
            'price_from': '3400.00',
            'currency': 'USD',
            'cover_image': SimpleUploadedFile('cover.jpg', create_test_image(), content_type='image/jpeg'),
            'video_file': SimpleUploadedFile('trip.mp4', b'fake video data', content_type='video/mp4'),
        }
        response = self.client.post('/api/travel-content/admin/curated-trips/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CuratedTrip.objects.count(), 1)

    def test_admin_can_update_travel_reel(self):
        """Test that admin can update a TravelReel's text fields via PATCH."""
        self.client.force_authenticate(user=self.admin_user)
        reel = TravelReel.objects.create(
            title='Old Title',
            media_type='image',
            destination=self.destination,
            cover_image=SimpleUploadedFile('cover.jpg', create_test_image(), content_type='image/jpeg'),
        )
        response = self.client.patch(
            f'/api/travel-content/admin/reels/{reel.id}/',
            {'title': 'New Title'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reel.refresh_from_db()
        self.assertEqual(reel.title, 'New Title')

    def test_admin_can_delete_travel_reel(self):
        """Test that admin can delete a TravelReel."""
        self.client.force_authenticate(user=self.admin_user)
        reel = TravelReel.objects.create(
            title='To Delete',
            media_type='image',
            destination=self.destination,
            cover_image=SimpleUploadedFile('cover.jpg', create_test_image(), content_type='image/jpeg'),
        )
        response = self.client.delete(f'/api/travel-content/admin/reels/{reel.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(TravelReel.objects.filter(id=reel.id).count(), 0)

    def test_admin_can_retrieve_single_travel_reel(self):
        """Test that admin can retrieve a single TravelReel."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create a reel directly (bypassing serializer validation for test purposes)
        reel = TravelReel.objects.create(
            title='Test Reel',
            media_type='image',
            destination=self.destination,
            cover_image=SimpleUploadedFile(
                'test.jpg', create_test_image(), content_type='image/jpeg'
            )
        )
        
        response = self.client.get(f'/api/travel-content/admin/reels/{reel.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(reel.id))
