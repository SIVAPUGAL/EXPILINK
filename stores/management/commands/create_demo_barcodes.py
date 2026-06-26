from django.core.management.base import BaseCommand
from stores.models import BarcodeProduct

DEMOS = [
    ('890001','Milk Packet','Dairy', 'Default', 20.0),
    ('890002','Bread','Bakery', 'Default', 15.0),
    ('890003','Biscuit','Snacks', 'Default', 10.0),
    ('890004','Yogurt Cup','Dairy', 'Default', 12.0),
    ('890005','Butter','Dairy', 'Default', 40.0),
    ('890006','Cheese','Dairy', 'Default', 60.0),
    ('890007','Apple Juice','Beverages', 'Default', 30.0),
    ('890008','Orange Juice','Beverages', 'Default', 30.0),
    ('890009','Lays Chips','Snacks', 'Default', 25.0),
    ('890010','Chocolate','Confectionery', 'Default', 50.0),
]

class Command(BaseCommand):
    help = 'Create demo BarcodeProduct entries for scanner testing'

    def handle(self, *args, **options):
        created = 0
        for code, name, category, supplier, price in DEMOS:
            obj, ok = BarcodeProduct.objects.get_or_create(barcode=code, defaults={'product_name': name, 'category': category, 'supplier': supplier, 'price': price})
            if ok:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created {code} -> {name}'))
            else:
                self.stdout.write(f'Exists {code} -> {name}')
        self.stdout.write(self.style.SUCCESS(f'Done. {created} created.'))
