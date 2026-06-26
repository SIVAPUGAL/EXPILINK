from django.db import models
from datetime import date


class Store(models.Model):
    store_name = models.CharField(max_length=100)
    owner_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    location = models.CharField(max_length=200)

    latitude = models.FloatField(default=0)
    longitude = models.FloatField(default=0)

    def __str__(self):
        return self.store_name


class Product(models.Model):

    product_name = models.CharField(max_length=100)
    category = models.CharField(
    max_length=100,
    default="General"
)
    supplier = models.CharField(
    max_length=100,
    default="Unknown"
)
    barcode = models.CharField(
    max_length=50,
    blank=True,
    null=True,
    unique=True
)
    batch_number = models.CharField(max_length=50)
    incoming_date = models.DateField()
    expiry_date = models.DateField()

    quantity = models.IntegerField()

    price = models.FloatField(default=0)

    demand = models.IntegerField(default=0)

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.product_name

    @property
    def days_left(self):
        return (self.expiry_date - date.today()).days

    @property
    def alert_level(self):
        if self.days_left <= 7:
            return "URGENT"
        elif self.days_left <= 30:
            return "WARNING"
        else:
            return "SAFE"

    @property
    def potential_loss(self):
        return self.quantity * self.price
class Transfer(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    from_store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='from_store'
    )

    to_store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='to_store'
    )

    quantity = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
    )
    status = models.CharField(
        max_length=20,
        default='PENDING'
    )

    def __str__(self):
        return f"{self.product} Transfer"
@property
def alert_level(self):
    if self.days_left <= 7:
        return "URGENT"
    elif self.days_left <= 30:
        return "WARNING"
    else:
        return "SAFE"
class Request(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE
    )

    product_name = models.CharField(max_length=100)

    quantity_needed = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store} needs {self.product_name}"
class Offer(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    buyer_store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='buyer_offers'
    )

    seller_store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='seller_offers'
    )

    quantity = models.IntegerField()

    offered_price = models.FloatField()

    status = models.CharField(
        max_length=20,
        default='PENDING'
    )

    def __str__(self):
        return f"{self.product} - ₹{self.offered_price}"
    product_image = models.ImageField(
    upload_to='products/',
    blank=True,
    null=True
)
class BarcodeProduct(models.Model):

    barcode = models.CharField(max_length=50)

    product_name = models.CharField(max_length=100)

    category = models.CharField(max_length=100)

    supplier = models.CharField(max_length=100)

    price = models.FloatField()

    def __str__(self):
        return self.product_name


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity_sold = models.IntegerField()
    sale_date = models.DateTimeField(auto_now_add=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    total_amount = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-sale_date']

    def __str__(self):
        return f"{self.product.product_name} — {self.quantity_sold} @ {self.sale_date.date()}"


class ScanRecord(models.Model):
    barcode = models.CharField(max_length=50)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    mode = models.CharField(max_length=20, choices=(('inventory','Inventory'),('sales','Sales')), default='inventory')
    quantity = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scan {self.barcode} ({self.mode}) @ {self.created_at}"