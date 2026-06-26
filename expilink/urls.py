from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static

from stores.views import (
    login_page,
    logout_page,
    dashboard,
    alerts,
    products,
    requests_page,
    transfers,
    matching,
    analytics,
    barcode_scan
)
from stores.views import settings_page
from stores.views import api_scan
from stores.views import api_lookup

urlpatterns = [

    # Login
    # Provide an explicit /login/ route and redirect root to it so
    # opening http://localhost:8000/ lands on the login page.
    path('login/', login_page, name='login'),
    path('', RedirectView.as_view(url='/login/', permanent=False)),

    # Logout
    path('logout/', logout_page, name='logout'),

    # Admin
    path('admin/', admin.site.urls),

    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),

    # Products
    path('products/', products, name='products'),

    # Alerts
    path('alerts/', alerts, name='alerts'),

    # Requests
    path('requests/', requests_page, name='requests'),

    # Matching
    path('matching/', matching, name='matching'),

    # Transfers
    path('transfers/', transfers, name='transfers'),

    # Analytics
    path('analytics/', analytics, name='analytics'),

    # Barcode Scan
    path('barcode-scan/', barcode_scan, name='barcode_scan'),
    # Settings
    path('settings/', settings_page, name='settings'),
    path('api/scan/', api_scan, name='api_scan'),
    path('api/lookup/', api_lookup, name='api_lookup'),
    path('barcode-lookup/', api_lookup, name='barcode_lookup')

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )