from django.contrib import admin
from .models import Drug, Batch, Sale, SaleItem, DisposalLog

# Register your database tables here so they appear in the admin panel
admin.site.register(Drug)
admin.site.register(Batch)
admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(DisposalLog)