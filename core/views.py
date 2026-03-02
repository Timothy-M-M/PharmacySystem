from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Drug, Batch, Transaction, SaleItem
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout

@login_required(login_url='/admin/login/')
def dashboard(request):
    # Base summary
    total_drugs = Drug.objects.count()
    total_batches = Batch.objects.count()
    
    # Calculate dates for the Expiry Alert System
    today = date.today()
    thirty_days = today + timedelta(days=30)
    sixty_days = today + timedelta(days=60)
    ninety_days = today + timedelta(days=90)
    
    # Filter the database based on the tiers
    expired = Batch.objects.filter(expiry_date__lte=today)
    critical = Batch.objects.filter(expiry_date__gt=today, expiry_date__lte=thirty_days)
    warning = Batch.objects.filter(expiry_date__gt=thirty_days, expiry_date__lte=sixty_days)
    advisory = Batch.objects.filter(expiry_date__gt=sixty_days, expiry_date__lte=ninety_days)
    
    context = {
        'total_drugs': total_drugs,
        'total_batches': total_batches,
        'expired_count': expired.count(),
        'critical_count': critical.count(),
        'warning_count': warning.count(),
        'advisory_count': advisory.count(),
    }
    
    return render(request, 'core/dashboard.html', context)




@login_required(login_url='/admin/login/')
def inventory(request):
    # Grab all batches and sort them by expiry date (earliest first)
    batches = Batch.objects.all().order_by('expiry_date')
    
    context = {
        'batches': batches,
    }
    return render(request, 'core/inventory.html', context)



@login_required(login_url='/admin/login/')
def pos(request):
    if request.method == 'POST':
        drug_id = request.POST.get('drug_id')
        requested_quantity = int(request.POST.get('quantity'))

        try:
            drug = Drug.objects.get(id=drug_id)
        except Drug.DoesNotExist:
            messages.error(request, "Selected drug does not exist.")
            return redirect('pos')

        # FIFO LOGIC: Get batches that are NOT expired, have stock > 0, ordered by closest expiry date
        today = date.today()
        available_batches = Batch.objects.filter(
            drug=drug,
            quantity__gt=0,
            expiry_date__gt=today
        ).order_by('expiry_date')

        # Calculate total available stock across all batches
        total_stock = sum(batch.quantity for batch in available_batches)

        # Constraint check: Prevent sale if asking for more than we have
        if requested_quantity > total_stock:
            messages.error(request, f"Insufficient stock! Only {total_stock} available across unexpired batches.")
            return redirect('pos')

        # Process the sale safely using a database transaction
        try:
            with transaction.atomic():
                # Create the main transaction header
                new_txn = Transaction.objects.create(user=request.user)
                total_amount = 0
                qty_to_fulfill = requested_quantity

                # Loop through batches (oldest first) and deduct stock
                for batch in available_batches:
                    if qty_to_fulfill <= 0:
                        break # Done fulfilling!

                    if batch.quantity >= qty_to_fulfill:
                        # This single batch has enough to fulfill the rest of the request
                        SaleItem.objects.create(
                            transaction=new_txn,
                            batch=batch,
                            quantity_sold=qty_to_fulfill,
                            price_at_sale=batch.unit_price
                        )
                        total_amount += (qty_to_fulfill * batch.unit_price)
                        batch.quantity -= qty_to_fulfill
                        batch.save()
                        qty_to_fulfill = 0 
                    else:
                        # This batch doesn't have enough, so drain it to 0 and move to the next oldest batch
                        SaleItem.objects.create(
                            transaction=new_txn,
                            batch=batch,
                            quantity_sold=batch.quantity,
                            price_at_sale=batch.unit_price
                        )
                        total_amount += (batch.quantity * batch.unit_price)
                        qty_to_fulfill -= batch.quantity
                        batch.quantity = 0
                        batch.save()

                # Save the final calculated total amount to the receipt header
                new_txn.total_amount = total_amount
                new_txn.save()

                # Send a success message to the screen
                messages.success(request, f"Sale successful! Total: KES {total_amount}. Stock automatically deducted using FIFO.")
                return redirect('pos')
                
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return redirect('pos')

    # If it's just a normal page load (GET request), show the form
    drugs = Drug.objects.all().order_by('drug_name')
    context = {'drugs': drugs}
    return render(request, 'core/pos.html', context)


@login_required(login_url='/admin/login/')
def add_batch(request):
    if request.method == 'POST':
        # Grab all the data from the HTML form
        drug_id = request.POST.get('drug_id')
        batch_number = request.POST.get('batch_number')
        mfg_date = request.POST.get('mfg_date')
        expiry_date = request.POST.get('expiry_date')
        quantity = request.POST.get('quantity')
        unit_price = request.POST.get('unit_price')
        supplier_name = request.POST.get('supplier_name')

        try:
            drug = Drug.objects.get(id=drug_id)
            
            # Create the new batch in memory
            new_batch = Batch(
                drug=drug,
                batch_number=batch_number,
                mfg_date=mfg_date,
                expiry_date=expiry_date,
                quantity=quantity,
                unit_price=unit_price,
                supplier_name=supplier_name
            )
            
            # Run the clean() function from our models.py to check the date math
            new_batch.full_clean() 
            new_batch.save() # Save to database
            
            messages.success(request, f"Batch {batch_number} added successfully!")
            return redirect('inventory')
            
        except ValidationError as e:
            # If the date is expired, this catches the error and sends it to the screen
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, error)
            else:
                for error in e.messages:
                    messages.error(request, error)
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

    # For a normal page load, just send the list of drugs for the dropdown
    drugs = Drug.objects.all().order_by('drug_name')
    return render(request, 'core/add_batch.html', {'drugs': drugs})




@login_required(login_url='/admin/login/')
def reports(request):
    # Fetch recent sales (ordered by newest first)
    recent_sales = Transaction.objects.all().order_by('-transaction_date')[:50]
    
    # Fetch critical and expired stock for the Expiry Report (<= 30 days)
    today = date.today()
    thirty_days = today + timedelta(days=30)
    critical_stock = Batch.objects.filter(expiry_date__lte=thirty_days).order_by('expiry_date')
    
    context = {
        'recent_sales': recent_sales,
        'critical_stock': critical_stock,
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




@login_required(login_url='/admin/login/')
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