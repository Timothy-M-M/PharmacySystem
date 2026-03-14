from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Drug, Batch, Transaction, SaleItem
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
User = get_user_model()

@login_required(login_url='login')
def dashboard(request):
    from .models import Drug, Batch, Sale # Make sure Sale is imported!
    from django.db.models import Sum      # The tool that adds up the money
    from datetime import date, timedelta
    
    today = date.today()
    thirty_days = today + timedelta(days=30)

    # 1. Calculate Real Inventory Metrics
    total_drugs = Drug.objects.count()
    active_batches = Batch.objects.filter(quantity__gt=0).count()
    low_stock = Batch.objects.filter(quantity__lt=20, quantity__gt=0).count()
    expired_count = Batch.objects.filter(expiry_date__lt=today).count()
    expiring_soon = Batch.objects.filter(expiry_date__gte=today, expiry_date__lte=thirty_days).count()

    # 2. Calculate Total Live Revenue
    # This goes into the Sale table and adds up all the 'total_amount' numbers
    revenue_data = Sale.objects.aggregate(Sum('total_amount'))
    total_revenue = revenue_data['total_amount__sum'] or 0.00 

    context = {
        'total_drugs': total_drugs,
        'active_batches': active_batches,
        'low_stock': low_stock,
        'expired_count': expired_count,
        'expiring_soon': expiring_soon,
        'total_revenue': total_revenue, # Sends the money to the HTML
    }
    
    return render(request, 'core/dashboard.html', context)




@login_required(login_url='login')
def inventory(request):
    # Grab all batches and sort them by expiry date (earliest first)
    batches = Batch.objects.all().order_by('expiry_date')
    
    context = {
        'batches': batches,
    }
    return render(request, 'core/inventory.html', context)



@login_required(login_url='login')
def pos(request):
    from .models import Drug, Batch, Sale, SaleItem
    from django.db.models import Sum
    
    if 'cart' not in request.session:
        request.session['cart'] = []
        
    cart = request.session['cart']
    
    if request.method == 'POST':
        # --- ADD TO CART LOGIC ---
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
            
        # --- SMART CHECKOUT LOGIC (FEFO) ---
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
    
    # Bundle the drugs for the HTML Dropdown
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
def add_batch(request):
    from .models import Drug, Batch
    
    if request.method == 'POST':
        try:
            # 1. Grab all the exact data from the new HTML form
            drug_id = request.POST.get('drug_id')
            batch_number = request.POST.get('batch_number')
            quantity = request.POST.get('quantity')
            unit_price = request.POST.get('unit_price')
            mfg_date = request.POST.get('mfg_date')
            expiry_date = request.POST.get('expiry_date')

            # 2. Find the correct drug in the database
            drug = Drug.objects.get(id=drug_id)
            
            # 3. Create the new stock batch
            Batch.objects.create(
                drug=drug,
                batch_number=batch_number,
                quantity=quantity,
                unit_price=unit_price,
                mfg_date=mfg_date,
                expiry_date=expiry_date
            )
            
            # 4. Show success and return to inventory
            messages.success(request, f"Batch {batch_number} received successfully!")
            return redirect('inventory')
            
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")
            
    # If just visiting the page, send the list of drugs for the dropdown
    drugs = Drug.objects.all()
    return render(request, 'core/add_batch.html', {'drugs': drugs})




@login_required(login_url='login')
def reports(request):
    from .models import Batch, Sale, DisposalLog
    from django.db.models import Sum
    
    # 1. Do the math (Summary)
    total_rev = Sale.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    sales_count = Sale.objects.count()
    active_inv = Batch.objects.filter(quantity__gt=0).count()
    disposed_count = DisposalLog.objects.count()
    
    # 2. Fetch the detailed lists (Latest data first)
    # Grabbing the top 50 recent transactions to keep the PDF manageable
    sales_list = Sale.objects.all().order_by('-date_added')[:50] 
    inventory_list = Batch.objects.filter(quantity__gt=0).order_by('expiry_date')
    disposal_list = DisposalLog.objects.all().order_by('-date_disposed')
    acquisition_list = Batch.objects.all().order_by('-id')[:50]
    
    # 3. Package it all
    context = {
        'total_revenue': total_rev,
        'total_sales_count': sales_count,
        'active_inventory': active_inv,
        'total_disposed': disposed_count,
        'sales_list': sales_list,
        'inventory_list': inventory_list,
        'disposal_list': disposal_list,
        'acquisition_list': acquisition_list,
    }
    
    return render(request, 'core/reports.html', context)




def custom_login(request):
    # If they are already logged in, send them straight to the dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # Check if the credentials match the database
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




@login_required(login_url='login')
def receipt(request, txn_id):
    try:
        # Fetch the main transaction header
        transaction_record = Transaction.objects.get(id=txn_id)
        # Fetch all the items sold in this specific transaction
        sold_items = SaleItem.objects.filter(transaction=transaction_record)
        
        context = {
            'transaction': transaction_record,
            'sold_items': sold_items,
        }
        return render(request, 'core/receipt.html', context)
        
    except Transaction.DoesNotExist:
        messages.error(request, "Receipt not found.")
        return redirect('reports')
    
    
    
@login_required(login_url='login')
def add_drug(request):
    if request.method == 'POST':
        drug_name = request.POST.get('drug_name')
        description = request.POST.get('description')
        unit = request.POST.get('unit')
        
        try:
            # Check if drug already exists (case-insensitive)
            if Drug.objects.filter(drug_name__iexact=drug_name).exists():
                messages.error(request, f"The medication '{drug_name}' is already registered in the catalog.")
            else:
                # Save the brand new drug
                Drug.objects.create(
                    drug_name=drug_name,
                    unit=unit
                )
                messages.success(request, f"'{drug_name}' registered successfully! You can now add batches for it.")
                return redirect('inventory')
                
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            
    return render(request, 'core/add_drug.html')



@login_required(login_url='login')
def manage_staff(request):
    # Security check: Only Admins (superusers) can view this page
    if not request.user.is_superuser:
        messages.error(request, "Access Denied: Only Administrators can manage staff.")
        return redirect('dashboard')
    
    # Get all registered users
    staff_members = User.objects.all()
    return render(request, 'core/manage_staff.html', {'staff_members': staff_members})

@login_required(login_url='login')
def add_staff(request):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied: Only Administrators can add staff.")
        return redirect('dashboard')

    if request.method == 'POST':
        u_name = request.POST.get('username')
        p_word = request.POST.get('password')
        email = request.POST.get('email')
        
        # Check if username is already taken
        if User.objects.filter(username=u_name).exists():
            messages.error(request, f"The username '{u_name}' is already taken.")
        else:
            # Create the standard cashier account
            User.objects.create_user(username=u_name, email=email, password=p_word)
            messages.success(request, f"Cashier account '{u_name}' created successfully!")
            return redirect('manage_staff')

    return render(request, 'core/add_staff.html')





@login_required(login_url='login') 
def dispose_batch(request, batch_id):
    from .models import Batch, DisposalLog
    batch = Batch.objects.get(id=batch_id)
    
    if request.method == 'POST':
        qty = int(request.POST.get('dispose_quantity'))
        reason = request.POST.get('reason')
        
        # 1. Write to the permanent Audit Log
        DisposalLog.objects.create(
            drug_name=batch.drug.drug_name,
            batch_number=batch.batch_number,
            quantity=qty,
            reason=reason,
            disposed_by=request.user
        )
        
        # 2. Deduct the physical stock
        batch.quantity -= qty
        batch.save()
        messages.success(request, f"Disposed {qty} units of {batch.drug.drug_name}.")
        return redirect('inventory')
        
    return render(request, 'core/dispose_batch.html', {'batch': batch})

@login_required(login_url='login')
def audit_log(request):
    from .models import DisposalLog
    logs = DisposalLog.objects.all().order_by('-date_disposed')
    return render(request, 'core/audit_log.html', {'logs': logs})


@login_required(login_url='login')
def receipt(request, sale_id):
    from .models import Sale
    # Fetch the specific sale and all its attached items
    sale = Sale.objects.get(id=sale_id)
    return render(request, 'core/receipt.html', {'sale': sale})



@login_required(login_url='login')
def alerts(request):
    from .models import Batch
    from datetime import date
    today = date.today()
    
    # 1. Fetch strictly EXPIRED items (Disposal needed)
    expired_batches = Batch.objects.filter(expiry_date__lt=today)
    
    # 2. Fetch strictly LOW STOCK items (Restock needed)
    low_stock_batches = Batch.objects.filter(quantity__lt=20, quantity__gt=0)
    
    return render(request, 'core/alerts.html', {
        'expired_batches': expired_batches,
        'low_stock_batches': low_stock_batches
    })



@login_required(login_url='login')
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