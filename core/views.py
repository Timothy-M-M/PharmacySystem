from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from .models import Drug, Batch, Transaction, SaleItem
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model

User = get_user_model()

# ==========================================
# SECURITY BOUNCERS
# ==========================================
def is_manager(user):
    return user.is_staff

# ==========================================
# AUTHENTICATION VIEWS
# ==========================================
def custom_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'core/login.html')

def custom_logout(request):
    logout(request)
    return redirect('login')


# ==========================================
# PUBLIC VIEWS (Accessible by Cashiers)
# ==========================================
@login_required(login_url='login')
def pos(request):
    from .models import Drug, Batch, Sale, SaleItem
    from django.db.models import Sum
    
    if 'cart' not in request.session:
        request.session['cart'] = []
        
    cart = request.session['cart']
    
    if request.method == 'POST':
        if 'add_to_cart' in request.POST:
            drug_id = request.POST.get('drug_id')
            quantity = int(request.POST.get('quantity', 1))
            
            try:
                drug = Drug.objects.get(id=drug_id)
                total_stock = Batch.objects.filter(drug=drug, quantity__gt=0).aggregate(Sum('quantity'))['quantity__sum'] or 0
                
                if total_stock >= quantity:
                    oldest_batch = Batch.objects.filter(drug=drug, quantity__gt=0).order_by('expiry_date').first()
                    price = oldest_batch.unit_price
                    
                    cart.append({
                        'drug_id': drug.id,
                        'drug_name': drug.drug_name,
                        'price': str(price),
                        'quantity': quantity,
                        'total': str(price * quantity)
                    })
                    request.session.modified = True
                    messages.success(request, f"Added {quantity} units to cart.")
                else:
                    messages.error(request, f"Only {total_stock} units available!")
            except Drug.DoesNotExist:
                messages.error(request, "Product not found.")
            return redirect('pos')
            
        elif 'checkout' in request.POST:
            if cart:
                total_amount = sum(float(item['total']) for item in cart)
                sale = Sale.objects.create(cashier=request.user, total_amount=total_amount)
                
                for item in cart:
                    qty_needed = int(item['quantity'])
                    batches = Batch.objects.filter(drug_id=item['drug_id'], quantity__gt=0).order_by('expiry_date')
                    
                    for batch in batches:
                        if qty_needed <= 0:
                            break
                        qty_to_take = min(batch.quantity, qty_needed)
                        SaleItem.objects.create(sale=sale, batch=batch, quantity=qty_to_take, price=item['price'])
                        batch.quantity -= qty_to_take
                        batch.save()
                        qty_needed -= qty_to_take
                        
                request.session['cart'] = []
                request.session.modified = True
                messages.success(request, f"Payment Processed! KES {total_amount} recorded.")
                return redirect('receipt', sale_id=sale.id)

    total_amount = sum(float(item['total']) for item in cart)
    
    active_drugs = []
    drugs = Drug.objects.filter(batch__quantity__gt=0).distinct()
    for drug in drugs:
        total_stock = Batch.objects.filter(drug=drug, quantity__gt=0).aggregate(Sum('quantity'))['quantity__sum']
        oldest_batch = Batch.objects.filter(drug=drug, quantity__gt=0).order_by('expiry_date').first()
        if total_stock and oldest_batch:
            active_drugs.append({'id': drug.id, 'name': drug.drug_name, 'price': oldest_batch.unit_price, 'stock': total_stock})
            
    return render(request, 'core/pos.html', {
        'active_drugs': active_drugs,
        'cart': cart,
        'total_amount': total_amount
    })


@login_required(login_url='login')
def receipt(request, sale_id):
    from .models import Sale, SaleItem
    sale = Sale.objects.get(id=sale_id)
    items = SaleItem.objects.filter(sale=sale) 
    context = {
        'sale': sale,
        'items': items,
    }
    return render(request, 'core/receipt.html', context)


# ==========================================
# RESTRICTED VIEWS (Managers & Admins Only)
# ==========================================
@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def dashboard(request):
    from .models import Drug, Batch, Sale 
    from django.db.models import Sum      
    from datetime import date, timedelta
    
    today = date.today()
    thirty_days = today + timedelta(days=30)

    total_drugs = Drug.objects.count()
    active_batches = Batch.objects.filter(quantity__gt=0).count()
    
    # [FIX] Only count expired batches that still have physical stock
    expired_count = Batch.objects.filter(expiry_date__lt=today, quantity__gt=0).count()
    expiring_soon = Batch.objects.filter(expiry_date__gte=today, expiry_date__lte=thirty_days, quantity__gt=0).count()

    # [FIX] Calculate low stock by checking the TOTAL drug quantity, not individual batches
    low_stock = 0
    for drug in Drug.objects.all():
        total = Batch.objects.filter(drug=drug, quantity__gt=0).aggregate(Sum('quantity'))['quantity__sum'] or 0
        if 0 < total < 20:
            low_stock += 1

    revenue_data = Sale.objects.aggregate(Sum('total_amount'))
    total_revenue = revenue_data['total_amount__sum'] or 0.00 

    context = {
        'total_drugs': total_drugs,
        'active_batches': active_batches,
        'low_stock': low_stock,
        'expired_count': expired_count,
        'expiring_soon': expiring_soon,
        'total_revenue': total_revenue, 
    }
    
    return render(request, 'core/dashboard.html', context)


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def alerts(request):
    from .models import Drug, Batch
    from django.db.models import Sum
    from datetime import date
    today = date.today()
    
    # [FIX] Hide expired batches if they have already been disposed (quantity = 0)
    expired_batches = Batch.objects.filter(expiry_date__lt=today, quantity__gt=0)
    
    # [FIX] Check low stock for the whole drug, resolving the alert if a new batch is added
    low_stock_drugs = []
    for drug in Drug.objects.all():
        total_stock = Batch.objects.filter(drug=drug, quantity__gt=0).aggregate(Sum('quantity'))['quantity__sum'] or 0
        if 0 < total_stock < 20:
            low_stock_drugs.append({
                'drug_name': drug.drug_name,
                'total_stock': total_stock,
                'unit': drug.unit
            })
            
    return render(request, 'core/alerts.html', {
        'expired_batches': expired_batches,
        'low_stock_drugs': low_stock_drugs
    })


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def inventory(request):
    batches = Batch.objects.all().order_by('expiry_date')
    return render(request, 'core/inventory.html', {'batches': batches})


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def add_batch(request):
    from .models import Drug, Batch
    if request.method == 'POST':
        try:
            drug_id = request.POST.get('drug_id')
            batch_number = request.POST.get('batch_number')
            quantity = request.POST.get('quantity')
            unit_price = request.POST.get('unit_price')
            mfg_date = request.POST.get('mfg_date')
            expiry_date = request.POST.get('expiry_date')

            drug = Drug.objects.get(id=drug_id)
            Batch.objects.create(drug=drug, batch_number=batch_number, quantity=quantity, unit_price=unit_price, mfg_date=mfg_date, expiry_date=expiry_date)
            messages.success(request, f"Batch {batch_number} received successfully!")
            return redirect('inventory')
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")
            
    drugs = Drug.objects.all()
    return render(request, 'core/add_batch.html', {'drugs': drugs})


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def reports(request):
    from .models import Batch, Sale, DisposalLog
    from django.db.models import Sum
    
    total_rev = Sale.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    sales_count = Sale.objects.count()
    active_inv = Batch.objects.filter(quantity__gt=0).count()
    disposed_count = DisposalLog.objects.count()
    
    sales_list = Sale.objects.all().order_by('-date_added')[:50] 
    inventory_list = Batch.objects.filter(quantity__gt=0).order_by('expiry_date')
    disposal_list = DisposalLog.objects.all().order_by('-date_disposed')
    acquisition_list = Batch.objects.all().order_by('-id')[:50]
    
    context = {
        'total_revenue': total_rev, 'total_sales_count': sales_count,
        'active_inventory': active_inv, 'total_disposed': disposed_count,
        'sales_list': sales_list, 'inventory_list': inventory_list,
        'disposal_list': disposal_list, 'acquisition_list': acquisition_list,
    }
    return render(request, 'core/reports.html', context)


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def add_drug(request):
    if request.method == 'POST':
        drug_name = request.POST.get('drug_name')
        description = request.POST.get('description')
        unit = request.POST.get('unit')
        
        try:
            if Drug.objects.filter(drug_name__iexact=drug_name).exists():
                messages.error(request, f"The medication '{drug_name}' is already registered in the catalog.")
            else:
                Drug.objects.create(drug_name=drug_name, unit=unit)
                messages.success(request, f"'{drug_name}' registered successfully!")
                return redirect('inventory')
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            
    return render(request, 'core/add_drug.html')


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def dispose_batch(request, batch_id):
    from .models import Batch, DisposalLog
    batch = Batch.objects.get(id=batch_id)
    
    if request.method == 'POST':
        qty = int(request.POST.get('dispose_quantity'))
        reason = request.POST.get('reason')
        
        DisposalLog.objects.create(drug_name=batch.drug.drug_name, batch_number=batch.batch_number, quantity=qty, reason=reason, disposed_by=request.user)
        batch.quantity -= qty
        batch.save()
        messages.success(request, f"Disposed {qty} units of {batch.drug.drug_name}.")
        return redirect('inventory')
        
    return render(request, 'core/dispose_batch.html', {'batch': batch})


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def audit_log(request):
    from .models import DisposalLog
    logs = DisposalLog.objects.all().order_by('-date_disposed')
    return render(request, 'core/audit_log.html', {'logs': logs})


@login_required(login_url='login')
@user_passes_test(is_manager, login_url='pos')
def system_report(request):
    from .models import Drug, Batch, Sale, DisposalLog
    from django.db.models import Sum
    context = {
        'total_revenue': Sale.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'total_sales_count': Sale.objects.count(),
        'active_inventory': Batch.objects.filter(quantity__gt=0).count(),
        'total_disposed': DisposalLog.objects.count(),
    }
    return render(request, 'core/reports.html', context)


# ==========================================
# SUPERUSER ONLY VIEWS
# ==========================================
@login_required(login_url='login')
def manage_staff(request):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')
    staff_members = User.objects.all()
    return render(request, 'core/manage_staff.html', {'staff_members': staff_members})


@login_required(login_url='login')
def add_staff(request):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    if request.method == 'POST':
        u_name = request.POST.get('username')
        p_word = request.POST.get('password')
        email = request.POST.get('email')
        
        if User.objects.filter(username=u_name).exists():
            messages.error(request, f"Username '{u_name}' is already taken.")
        else:
            User.objects.create_user(username=u_name, email=email, password=p_word)
            messages.success(request, f"Account '{u_name}' created successfully!")
            return redirect('manage_staff')

    return render(request, 'core/add_staff.html')