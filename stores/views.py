from sys import path

from django.shortcuts import render
from .models import Store, Product, Transfer, Request, Offer
from django.shortcuts import render
from django.http import HttpResponse
from .models import BarcodeProduct
from .models import (
    Store,
    Product,
    Transfer,
    Request,
    Offer,
    BarcodeProduct
)

import pytesseract
from PIL import Image


def dashboard(request):
    from datetime import date, timedelta

    today = date.today()

    total_products = Product.objects.count()

    # fetch stores for Store Network card
    stores = Store.objects.all()
    total_stores = stores.count()

    # debug output to terminal
    print(f"[DEBUG] Store count: {total_stores}")

    expiring_products = Product.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lte=today + timedelta(days=30)
    ).order_by('expiry_date')

    expiring_products_count = expiring_products.count()

    transfer_count = Transfer.objects.count()

    request_count = Request.objects.count()

    # potential savings = sum of potential_loss for expiring products
    potential_savings = sum([p.potential_loss for p in expiring_products])

    # simple confidence metric: percent of expiring products relative to total (0-100)
    confidence_score = 0
    if total_products > 0:
        confidence_score = int((expiring_products_count / total_products) * 100)

    # simple alerts: one per expiring product
    alerts = []
    for p in expiring_products:
        # compute days_left safely
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        alerts.append({
            'title': f"{getattr(p, 'product_name', getattr(p, 'name', 'Unknown'))} — {days_left}d",
            'message': f"{getattr(p, 'product_name', getattr(p, 'name', 'Unknown'))} — {days_left} days left"
        })

    # Featured products: select up to 2 products closest to expiry and attach days_left and risk_status
    featured_qs = Product.objects.filter(expiry_date__isnull=False, expiry_date__gte=today).order_by('expiry_date')[:2]
    featured_products = []
    for p in featured_qs:
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        # determine risk_status per rules and attach as attribute
        if days_left is None:
            risk_status = 'SAFE'
        elif days_left <= 0:
            risk_status = 'CRITICAL'
        elif days_left <= 3:
            risk_status = 'HIGH RISK'
        elif days_left <= 7:
            risk_status = 'WARNING'
        else:
            risk_status = 'SAFE'
        # attach safe temporary attributes for template/logic (do NOT set `days_left` property)
        setattr(p, 'calculated_days_left', days_left)
        setattr(p, 'risk_status', risk_status)
        featured_products.append(p)

    # prepare alert_products with calculated fields for template usage
    alert_products_processed = []
    for p in expiring_products[:5]:
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        if days_left is None:
            risk_status = 'SAFE'
        elif days_left <= 0:
            risk_status = 'CRITICAL'
        elif days_left <= 3:
            risk_status = 'HIGH RISK'
        elif days_left <= 7:
            risk_status = 'WARNING'
        else:
            risk_status = 'SAFE'
        setattr(p, 'calculated_days_left', days_left)
        setattr(p, 'risk_status', risk_status)
        alert_products_processed.append(p)

    context = {
        'featured_products': featured_products,
        'near_expiry_count': expiring_products_count,
        'active_matches': transfer_count,
        'total_savings': potential_savings,
        'nearby_store_count': total_stores,
        'total_products': total_products,
        'ai_suggestion': None,
        'alert_products': alert_products_processed,
        'transfer_opps': [],
        'confidence_score': confidence_score,
        'request_count': request_count,
        'pending_request_count': request_count,
        'completed_transfers': transfer_count,
        'stores': stores,
        'total_stores': total_stores,
    }

    return render(request, 'dashboard.html', context)


def alerts(request):
    from datetime import date

    # show only products with expiry and sort by expiry ascending (expired first)
    qs = Product.objects.filter(expiry_date__isnull=False).order_by('expiry_date')

    # search
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(product_name__icontains=q)

    # filter by status
    status = request.GET.get('status', '').upper()
    today = date.today()
    if status == 'CRITICAL':
        qs = qs.filter(expiry_date__lte=today)
    elif status == 'URGENT' or status == 'WARNING':
        # warning: within 30 days
        from datetime import timedelta
        qs = qs.filter(expiry_date__lte=today + timedelta(days=30), expiry_date__gt=today)
    elif status == 'SAFE':
        from datetime import timedelta
        qs = qs.filter(expiry_date__gt=today + timedelta(days=30))
    elif status == 'EXPIRED':
        qs = qs.filter(expiry_date__lt=today)

    # sorting is already by expiry_date asc by default; allow optional reverse
    sort = request.GET.get('sort', 'expiry')
    if sort == 'days_desc':
        qs = qs.order_by('-expiry_date')

    # counts
    from datetime import timedelta
    critical_count = Product.objects.filter(expiry_date__lte=today + timedelta(days=7)).count()
    warning_count = Product.objects.filter(expiry_date__lte=today + timedelta(days=30), expiry_date__gt=today + timedelta(days=7)).count()
    safe_count = Product.objects.filter(expiry_date__gt=today + timedelta(days=30)).count()
    expired_count = Product.objects.filter(expiry_date__lt=today).count()
    # expired_count intentionally omitted to keep only three stats as requested

    # annotate days_left
    items = []
    seen = set()
    for p in qs:
        # skip duplicates by unique id or barcode
        key = (p.id, getattr(p, 'barcode', None))
        if key in seen:
            continue
        seen.add(key)
        days_left = (p.expiry_date - today).days if p.expiry_date else 9999
        if days_left < 0:
            st = 'EXPIRED'
        elif days_left <= 7:
            st = 'CRITICAL'
        elif days_left <= 30:
            st = 'WARNING'
        else:
            st = 'SAFE'
        items.append({
            'id': p.id,
            'product_name': p.product_name,
            'category': getattr(p, 'category', '') or '',
            'expiry_date': p.expiry_date,
            'days_left': days_left,
            'status': st,
            'quantity': getattr(p, 'quantity', 0),
            'barcode': getattr(p, 'barcode', '') or '',
            'updated_at': getattr(p, 'updated_at', None),
        })

    # Nearly expiry products (next 30 days, exclude already expired), limit 5
    from datetime import timedelta
    nearly_qs = Product.objects.filter(
        expiry_date__gt=today,
        expiry_date__lte=today + timedelta(days=30)
    ).order_by('expiry_date')[:5]

    nearly_items = []
    for p in nearly_qs:
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        if days_left is None or days_left < 0:
            continue
        nearly_items.append({
            'id': p.id,
            'product_name': p.product_name,
            'expiry_date': p.expiry_date,
            'days_left': days_left,
            'quantity': getattr(p, 'quantity', 0),
            'barcode': getattr(p, 'barcode', '') or '',
        })

    # provide names matching Products page so templates can reuse components
    product_count = Product.objects.count()
    low_stock = Product.objects.filter(quantity__lt=20).count()
    out_of_stock = Product.objects.filter(quantity=0).count()
    # New Added: products created/entered within the last 7 days
    try:
        from django.utils import timezone
        cutoff = timezone.now().date() - timedelta(days=7)
        new_added_count = Product.objects.filter(incoming_date__gte=cutoff).count()
    except Exception:
        # fallback if incoming_date or timezone not available
        new_added_count = 0
    near_expiry = new_added_count

    context = {
        'alerts': items,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'safe_count': safe_count,
        'expired_count': expired_count,
        'nearly_expiry': nearly_items,
        'query': q,
        'filter_status': status,
        'sort': sort,
        'product_count': product_count,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'near_expiry': near_expiry,
    }

    return render(request, 'alerts.html', context)


from datetime import date

products = Product.objects.all()

low_stock = products.filter(quantity__lt=20).count()

out_of_stock = products.filter(quantity=0).count()

new_arrivals = products.count()

context = {

    'products': products,

    'product_count': products.count(),

    'low_stock': low_stock,

    'out_of_stock': out_of_stock,

    'new_arrivals': new_arrivals,

}


def requests_page(request):
    from math import radians, cos, sin, asin, sqrt

    requests_qs = Request.objects.all()

    # determine current store by matching logged-in user's email if possible
    current_store = None
    try:
        if request.user and request.user.is_authenticated:
            current_store = Store.objects.filter(email__iexact=request.user.email).first()
    except Exception:
        current_store = None

    # Haversine distance (km)
    def haversine(lat1, lon1, lat2, lon2):
        # return distance in kilometers
        try:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            km = 6371 * c
            return km
        except Exception:
            return None

    # Nearby stores within 30 km excluding current store
    nearby_store_count = 0
    try:
        stores_qs = Store.objects.exclude(id=current_store.id) if current_store else Store.objects.all()
        if current_store and current_store.latitude and current_store.longitude:
            for s in stores_qs:
                if s.latitude is None or s.longitude is None:
                    continue
                dist = haversine(current_store.latitude, current_store.longitude, s.latitude, s.longitude)
                if dist is not None and dist <= 30:
                    nearby_store_count += 1
        else:
            # fallback: count all other stores
            nearby_store_count = stores_qs.count() if current_store else Store.objects.count()
            if current_store:
                # exclude current
                nearby_store_count = max(0, nearby_store_count)
    except Exception:
        nearby_store_count = Store.objects.exclude(id=getattr(current_store, 'id', None)).count() if current_store else Store.objects.count()

    # Total transfers with status completed
    total_transfers = Transfer.objects.filter(status__iexact='completed').count()

    # Active matches: collect requests from other stores where
    # - request.status == 'pending'
    # - current_store has product with same name (case-insensitive) and quantity > 0
    active_matches = []
    active_match_count = 0
    try:
        if current_store:
            other_requests = Request.objects.exclude(store=current_store).filter(status__iexact='pending')
            for req in other_requests:
                # case-insensitive product match in current store
                has_prod = Product.objects.filter(
                    store=current_store,
                    product_name__iexact=req.product_name,
                    quantity__gt=0
                ).exists()
                if has_prod:
                    active_matches.append(req)
            active_match_count = len(active_matches)
        else:
            active_matches = []
            active_match_count = 0
    except Exception:
        active_matches = []
        active_match_count = 0

    # annotate each request with flags for client-side filtering
    try:
        # prepare lookups
        available_products_set = set()
        if current_store:
            available_products_set = set(Product.objects.filter(store=current_store, quantity__gt=0).values_list('product_name', flat=True))

        for req in requests_qs:
            # nearby: check distance between req.store and current_store
            is_nearby = False
            try:
                if current_store and current_store.latitude and current_store.longitude and req.store.latitude and req.store.longitude:
                    dist = haversine(current_store.latitude, current_store.longitude, req.store.latitude, req.store.longitude)
                    if dist is not None and dist <= 30:
                        is_nearby = True
            except Exception:
                is_nearby = False

            # transfer: request status indicates approved or completed
            req_status = getattr(req, 'status', '')
            is_transfer = str(req_status).lower() in ('approved', 'completed')

            # match: requested product exists in current store with qty>0
            is_match = False
            try:
                if current_store and req.product_name in available_products_set:
                    is_match = True
            except Exception:
                is_match = False

            setattr(req, 'is_nearby', is_nearby)
            setattr(req, 'is_transfer', is_transfer)
            setattr(req, 'is_match', is_match)
    except Exception:
        for req in requests_qs:
            setattr(req, 'is_nearby', False)
            setattr(req, 'is_transfer', False)
            setattr(req, 'is_match', False)

    context = {
        'requests': requests_qs,
        'nearby_store_count': nearby_store_count,
        'total_transfers': total_transfers,
        'active_matches': active_matches,
        'active_match_count': active_match_count,
    }

    return render(request, 'requests.html', context)


def transfers(request):

    transfers = Transfer.objects.all()

    return render(
        request,
        'transfers.html',
        {'transfers': transfers}
    )


def matching(request):
    from datetime import date, timedelta
    from math import radians, cos, sin, asin, sqrt

    today = date.today()

    # determine current store by logged-in user, fallback to first store
    current_store = None
    try:
        if request.user and request.user.is_authenticated:
            current_store = Store.objects.filter(email__iexact=request.user.email).first()
    except Exception:
        current_store = None
    if not current_store:
        current_store = Store.objects.first()

    def haversine(lat1, lon1, lat2, lon2):
        try:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return 6371 * c
        except Exception:
            return None

    matches = []

    # Fetch all products (do not accidentally filter out everything)
    products = Product.objects.all().order_by('product_name')

    # Debug: total products found
    try:
        print("Products:", products.count())
    except Exception:
        print("Products: (could not count)")

    for p in products:
        # days left until expiry (large number if no expiry)
        days_left = (p.expiry_date - today).days if getattr(p, 'expiry_date', None) else 9999

        # Predicted demand: prefer `demand` field, else estimate from recent requests
        predicted = None
        try:
            predicted = getattr(p, 'demand', None)
            if predicted is None:
                recent_reqs = Request.objects.filter(product_name__iexact=p.product_name)
                if recent_reqs.exists():
                    predicted = int(sum([r.quantity_needed for r in recent_reqs]) / recent_reqs.count())
                else:
                    predicted = 0
        except Exception:
            predicted = 0

        # Recommended transfer: simple heuristic, do NOT filter by transfer>0
        try:
            transfer = max(int(getattr(p, 'quantity', 0)) - int(predicted) - 10, 0)
        except Exception:
            transfer = 0

        # Saved amount estimation
        try:
            saved_amount = transfer * (float(getattr(p, 'price', 0) or 0)
                                       if getattr(p, 'price', None) is not None else 0)
        except Exception:
            saved_amount = 0

        matches.append({
            'product': p,
            'predicted_demand': predicted,
            'recommended_transfer': transfer,
            'days_left': days_left,
            'saved_amount': saved_amount,
        })

    # Debug: total matches generated
    try:
        print("Matches:", len(matches))
    except Exception:
        print("Matches: (could not determine length)")

    return render(request, 'matching.html', {'matches': matches})


def settings_page(request):
    return render(request, 'settings.html')


def analytics(request):

    products = Product.objects.all()

    total_loss = 0

    for product in products:

        total_loss += product.potential_loss

    context = {

        'store_count': Store.objects.count(),

        'product_count': Product.objects.count(),

        'transfer_count': Transfer.objects.count(),

        'request_count': Request.objects.count(),

        'total_loss': total_loss,

        'products': products,

    }

    return render(
        request,
        'analytics.html',
        context
    )
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect

def login_page(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect("dashboard")

    return render(
        request,
        "login.html"
    )
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_page(request):

    logout(request)

    return redirect('login')


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from django.utils import timezone
from .models import ScanRecord


@csrf_exempt
@require_http_methods(['POST'])
def api_scan(request):
    """API endpoint to record a barcode scan and update product inventory.

    POST /api/scan/  JSON: {"barcode":"890001","mode":"inventory"}
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'error': 'invalid json'}, status=400)

    barcode = payload.get('barcode')
    mode = payload.get('mode') or 'inventory'
    try:
        qty = int(payload.get('qty', 1))
    except Exception:
        qty = 1

    if not barcode:
        return JsonResponse({'success': False, 'error': 'barcode required'}, status=400)

    # support demo mapping via BarcodeProduct if present
    with transaction.atomic():
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            template = BarcodeProduct.objects.filter(barcode=barcode).first()
            if template:
                # create a Product from template
                product = Product.objects.create(
                    product_name=template.product_name,
                    category=template.category or 'General',
                    supplier=getattr(template, 'supplier', ''),
                    barcode=template.barcode,
                    batch_number='DEMO',
                    incoming_date=timezone.now().date(),
                    expiry_date=timezone.now().date(),
                    quantity=0,
                    price=template.price or 0,
                    demand=0,
                    store=Store.objects.first()
                )

        if not product:
            return JsonResponse({'success': False, 'error': 'product not found'}, status=404)

        # Update quantity based on mode
        if mode in ('inventory', 'add'):
            product.quantity = (product.quantity or 0) + qty
            action = 'added'
        elif mode in ('sales', 'sell'):
            product.quantity = max(0, (product.quantity or 0) - qty)
            action = 'sold'
        else:
            return JsonResponse({'success': False, 'error': 'invalid mode'}, status=400)

        product.save()

        # create ScanRecord
        scan = ScanRecord.objects.create(
            barcode=barcode,
            product=product,
            mode='inventory' if mode in ('inventory','add') else 'sales',
            quantity=qty
        )

        return JsonResponse({'success': True, 'product': {
            'product_name': product.product_name,
            'barcode': product.barcode,
            'category': product.category,
            'quantity': product.quantity,
            'expiry_date': product.expiry_date.strftime('%d-%m-%Y') if product.expiry_date else ''
        }, 'scan_id': scan.id, 'action': action})

        product.save()

        # record scan
        ScanRecord.objects.create(barcode=barcode, product=product, mode=mode, quantity=qty)

        # compute stats
        total = Product.objects.count()
        low_stock = Product.objects.filter(quantity__lt=20).count()
        out_of_stock = Product.objects.filter(quantity=0).count()

        return JsonResponse({'success': True, 'product': product.product_name, 'id': product.id, 'quantity': product.quantity, 'stats': {'total': total, 'low_stock': low_stock, 'out_of_stock': out_of_stock}})


@require_http_methods(['GET'])
def api_lookup(request):
    barcode = request.GET.get('barcode')
    print('api_lookup received barcode=', barcode)
    if not barcode:
        return JsonResponse({'success': False, 'error': 'barcode required'}, status=400)
    product = Product.objects.filter(barcode=barcode).first()
    if not product:
        return JsonResponse({'success': False, 'error': 'not found'}, status=404)
    return JsonResponse({'success': True, 'product': {
        'product_name': product.product_name,
        'barcode': product.barcode,
        'category': product.category,
        'quantity': product.quantity,
        'incoming_date': product.incoming_date.isoformat() if product.incoming_date else None,
        'expiry_date': product.expiry_date.isoformat() if product.expiry_date else None,
        'days_left': product.days_left if hasattr(product, 'days_left') else None
    }})


@require_http_methods(["GET", "POST"])
def products(request):
    """Render products page, handle search and AJAX create from drawer."""
    from datetime import date

    # default ordering: expiry ascending (soonest first). Nulls last.
    from django.db.models import F
    qs = Product.objects.all().order_by(F('expiry_date').asc(nulls_last=True), 'product_name')

    query = request.GET.get('q')
    category = request.GET.get('category')
    expiry = request.GET.get('expiry')
    view_mode = request.GET.get('view')

    if query:
        qs = qs.filter(product_name__icontains=query) | qs.filter(category__icontains=query)

    if category and category != '':
        qs = qs.filter(category=category)

    # quick view modes from stat cards
    if view_mode == 'out_of_stock':
        qs = qs.filter(quantity=0)
    elif view_mode == 'low_stock':
        qs = qs.filter(quantity__lt=20)

    # expiry filter mapping
    from datetime import timedelta
    today = date.today()
    if expiry == 'expired':
        qs = qs.filter(expiry_date__lt=today)
    elif expiry == 'today':
        qs = qs.filter(expiry_date=today)
    elif expiry == 'within7':
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=7))
    elif expiry == 'within30':
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
    elif expiry == 'this_month':
        first = today.replace(day=1)
        # compute last day of month
        import calendar
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        qs = qs.filter(expiry_date__gte=first, expiry_date__lte=last)
    elif expiry == 'next_month':
        import calendar
        if today.month == 12:
            year = today.year + 1; month = 1
        else:
            year = today.year; month = today.month + 1
        first = today.replace(year=year, month=month, day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        qs = qs.filter(expiry_date__gte=first, expiry_date__lte=last)
    elif expiry == 'this_year':
        first = today.replace(month=1, day=1)
        last = today.replace(month=12, day=31)
        qs = qs.filter(expiry_date__gte=first, expiry_date__lte=last)

    # If POST -> create product (AJAX)
    if request.method == 'POST':
        # accept form-encoded or JSON
        name = request.POST.get('product_name') or request.POST.get('name')
        category_val = request.POST.get('category')
        quantity = request.POST.get('quantity')
        price = request.POST.get('price')
        expiry_date = request.POST.get('expiry_date')
        barcode_val = request.POST.get('barcode') or None
        batch_number = request.POST.get('batch_number')
        incoming_date = request.POST.get('incoming_date')
        supplier = request.POST.get('supplier')

        if not name:
            return JsonResponse({'error': 'product_name required'}, status=400)

        try:
            quantity_value = int(quantity or 0)
        except ValueError:
            return JsonResponse({'error': 'quantity must be a whole number'}, status=400)

        try:
            price_value = float(price or 0.0)
        except ValueError:
            return JsonResponse({'error': 'price must be a number'}, status=400)

        store = Store.objects.first()
        if not store:
            return JsonResponse({'error': 'No store configured'}, status=500)

        product = Product.objects.create(
            product_name=name,
            category=category_val or 'General',
            supplier=supplier or 'Unknown',
            barcode=barcode_val,
            batch_number=batch_number or f"MANUAL-{today.strftime('%Y%m%d%H%M%S')}",
            incoming_date=incoming_date or today,
            expiry_date=expiry_date or today,
            quantity=quantity_value,
            price=price_value,
            demand=0,
            store=store
        )

        return JsonResponse({'ok': True, 'id': product.id, 'product_name': product.product_name})

    # AJAX JSON response for live search/filter
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = []
        from datetime import date
        from datetime import timedelta
        # support special client views
        view = request.GET.get('view', '')
        if view == 'new_added':
            cutoff = date.today() - timedelta(days=7)
            qs = qs.filter(incoming_date__isnull=False, incoming_date__gte=cutoff).order_by('-incoming_date')
        for p in qs:
            # compute days since added (based on incoming_date)
            days_since_added = None
            if getattr(p, 'incoming_date', None):
                days_since_added = (date.today() - p.incoming_date).days

            data.append({
                'id': p.id,
                'product_name': p.product_name,
                'barcode': p.barcode,
                'category': p.category,
                'quantity': p.quantity,
                'price': float(p.price or 0),
                'incoming_date': p.incoming_date.isoformat() if getattr(p, 'incoming_date', None) else None,
                'days_since_added': days_since_added,
                'updated_at': p.updated_at.isoformat() if getattr(p, 'updated_at', None) else None,
            })

        expiring_this_week = Product.objects.filter(expiry_date__lte=date.today() + __import__('datetime').timedelta(days=7)).count()

        # include stats for client UI
        total = Product.objects.count()
        low_stock = Product.objects.filter(quantity__lt=20).count()
        out_of_stock = Product.objects.filter(quantity=0).count()

        return JsonResponse({'products': data, 'expiring_this_week': expiring_this_week, 'stats': {'total': total, 'low_stock': low_stock, 'out_of_stock': out_of_stock}})

    # categories list
    categories = Product.objects.values_list('category', flat=True).distinct()

    # compute stats
    total = Product.objects.count()
    low_stock = Product.objects.filter(quantity__lt=20).count()
    out_of_stock = Product.objects.filter(quantity=0).count()
    # New Added count: products with incoming_date within last 7 days
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=7)
    near_expiry = Product.objects.filter(incoming_date__isnull=False, incoming_date__gte=cutoff).count()
    expiring_week_count = 0

    context = {
        'products': qs,
        'categories': categories,
        'product_count': total,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'near_expiry': near_expiry,
        'expiring_week_count': expiring_week_count,
    }

    return render(request, 'products.html', context)
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_page(request):

    logout(request)

    return redirect('login')
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_page(request):

    logout(request)

    return redirect('login')
context = {
    'store_count': Store.objects.count(),
    'product_count': Product.objects.count(),
    'transfer_count': Transfer.objects.count(),
    'request_count': Request.objects.count(),
    'total_stores': Store.objects.count()
}
from datetime import date

from django.shortcuts import redirect

def barcode_scan(request):
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt
    from django.db import transaction
    import json

    # If JSON AJAX POST -> update/create product quantity
    if request.method == 'POST' and (request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = request.POST.dict()

        barcode = payload.get('barcode')
        mode = payload.get('mode') or 'add'
        qty = int(payload.get('qty') or 1)

        if not barcode:
            return JsonResponse({'ok': False, 'error': 'barcode required'}, status=400)

        # Try to find existing Product by barcode
        product = Product.objects.filter(barcode=barcode).first()

        with transaction.atomic():
            if product:
                # update quantity
                if mode == 'add':
                    product.quantity = (product.quantity or 0) + qty
                elif mode == 'sell':
                    product.quantity = max(0, (product.quantity or 0) - qty)
                product.save()
                return JsonResponse({'ok': True, 'action': 'updated', 'id': product.id, 'product_name': product.product_name})
            else:
                # attempt to find a BarcodeProduct template
                template = BarcodeProduct.objects.filter(barcode=barcode).first()
                if template:
                    p = Product.objects.create(
                        product_name=template.product_name,
                        category=template.category or '',
                        supplier=getattr(template, 'supplier', None),
                        barcode=template.barcode,
                        batch_number=payload.get('batch_number', 'DEMO'),
                        incoming_date=payload.get('incoming_date') or date.today(),
                        expiry_date=payload.get('expiry_date') or date.today(),
                        quantity=qty,
                        price=template.price or 0,
                        demand=0,
                        store=Store.objects.first()
                    )
                    return JsonResponse({'ok': True, 'action': 'created', 'id': p.id, 'product_name': p.product_name})
                else:
                    # create a minimal Product record for demo codes if none exist
                    p = Product.objects.create(
                        product_name=payload.get('product_name') or f'Product {barcode}',
                        category=payload.get('category') or 'Demo',
                        barcode=barcode,
                        incoming_date=payload.get('incoming_date') or date.today(),
                        expiry_date=payload.get('expiry_date') or None,
                        quantity=qty,
                        price=0,
                        demand=0,
                        store=Store.objects.first()
                    )
                    return JsonResponse({'ok': True, 'action': 'created', 'id': p.id, 'product_name': p.product_name})

    # Default: render scanner page
    return render(request, 'barcode_scan.html')