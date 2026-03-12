from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Drug, Batch
from datetime import date, timedelta

User = get_user_model()

class PharmacySystemTests(TestCase):
    def setUp(self):
        # 1. Create a simulated Administrator for testing
        self.admin_user = User.objects.create_superuser(
            username='testadmin',
            password='testpassword123',
            email='admin@test.com'
        )
        
        # 2. Create a simulated Medication
        self.drug = Drug.objects.create(
            drug_name='Aspirin 500mg',
            unit='Tablet'
        )
        
        # 3. Create a simulated Batch (Added mfg_date to satisfy the database!)
        self.batch = Batch.objects.create(
            drug=self.drug,
            batch_number='BATCH-001',
            quantity=100,
            unit_price=10.00,
            mfg_date=date.today() - timedelta(days=30),  # <--- Added this line!
            expiry_date=date.today() + timedelta(days=30)
        )

    def test_database_drug_creation(self):
        """Test T-01: Verify the system can register a new drug profile."""
        self.assertEqual(self.drug.drug_name, 'Aspirin 500mg')
        self.assertEqual(Drug.objects.count(), 1)

    def test_database_batch_creation(self):
        """Test T-02: Verify the system correctly links batches to parent drugs."""
        self.assertEqual(self.batch.quantity, 100)
        self.assertEqual(self.batch.drug.drug_name, 'Aspirin 500mg')
        self.assertTrue(self.batch.expiry_date > date.today())

    def test_security_anonymous_access_blocked(self):
        """Test T-03: Verify unauthenticated users are kicked out to the login screen."""
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_security_authenticated_access_allowed(self):
        """Test T-04: Verify logged-in users can successfully access the system."""
        self.client.login(username='testadmin', password='testpassword123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)