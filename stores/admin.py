from django.contrib import admin

from .models import (
    Store,
    Product,
    Transfer,
    Request,
    Offer,
    BarcodeProduct,
    Sale
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'barcode', 'category', 'quantity', 'price', 'store')
    search_fields = ('product_name', 'barcode', 'category')

admin.site.register(Store)
admin.site.register(Transfer)
admin.site.register(Request)
admin.site.register(Offer)
admin.site.register(BarcodeProduct)
admin.site.register(Sale)