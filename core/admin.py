from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from .models import Drug, Batch, Sale, SaleItem, DisposalLog

# 1. Fetch your User model safely
User = get_user_model()

# 2. Force the Users table to appear in the admin panel
try:
    admin.site.register(User, UserAdmin)
except admin.sites.AlreadyRegistered:
    # If Django already registered it in the background, just ignore and move on
    pass

# 3. Register all your Pharmacy System models
admin.site.register(Drug)
admin.site.register(Batch)
admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(DisposalLog)