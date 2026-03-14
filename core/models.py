from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone

# 1. User Entity 
class User(AbstractUser):
    ROLE_CHOICES = (
        ('Admin', 'Administrator'),
        ('Pharmacist', 'Pharmacist / Cashier'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Pharmacist')

    def __str__(self):
        return f"{self.username} ({self.role})"

# 2. Drug Entity 
class Drug(models.Model):
    drug_name = models.CharField(max_length=255)
    generic_name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    unit = models.CharField(max_length=50) 

    def __str__(self):
        return self.drug_name

# 3. Batch Entity 
class Batch(models.Model):
    drug = models.ForeignKey(Drug, on_delete=models.RESTRICT) 
    batch_number = models.CharField(max_length=100, unique=True)
    mfg_date = models.DateField("Manufacturing Date")
    expiry_date = models.DateField("Expiry Date")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) 
    supplier_name = models.CharField(max_length=255)
    date_added = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Data Integrity Rules to prevent past expiry dates [cite: 277, 278]
        if self.expiry_date and self.mfg_date and self.expiry_date <= self.mfg_date:
            raise ValidationError('Expiry date MUST be greater than the manufacturing date.')
        if self.expiry_date and self.pk is None and self.expiry_date <= timezone.now().date():
            raise ValidationError("Expiry date MUST be greater than today's date at the time of registration.")

    def __str__(self):
        return f"{self.drug.drug_name} - Batch: {self.batch_number}"

# 4. Transaction Entity 
class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    transaction_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"TXN-{self.id} on {self.transaction_date.strftime('%Y-%m-%d %H:%M')}"



    def __str__(self):
        return f"{self.quantity_sold}x {self.batch.drug.drug_name} (TXN-{self.transaction.id})"

# 6. AlertLog Entity 
class AlertLog(models.Model):
    TIER_CHOICES = (
        ('Critical', 'Critical (30 Days)'),
        ('Warning', 'Warning (60 Days)'),
        ('Advisory', 'Advisory (90 Days)'),
    )
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    alert_tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    generated_date = models.DateTimeField(auto_now_add=True)
    is_acknowledged = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_tier} Alert - {self.batch.batch_number}"
    
    
    
from django.contrib.auth import get_user_model
User = get_user_model()
class Sale(models.Model):
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Sale #{self.id} - KES {self.total_amount}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    batch = models.ForeignKey('Batch', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.quantity} units from Batch {self.batch.batch_number if self.batch else 'Unknown'}"
    
class DisposalLog(models.Model):
    drug_name = models.CharField(max_length=255)
    batch_number = models.CharField(max_length=100)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=255)
    disposed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_disposed = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.drug_name} - {self.reason}"