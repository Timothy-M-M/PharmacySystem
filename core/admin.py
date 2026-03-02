from django.contrib import admin
from .models import User, Drug, Batch, Transaction, SaleItem, AlertLog

# This tells Django to show these tables in your Admin panel [cite: 71, 230]
admin.site.register(User)
admin.site.register(Drug)
admin.site.register(Batch)
admin.site.register(Transaction)
admin.site.register(SaleItem)
admin.site.register(AlertLog)