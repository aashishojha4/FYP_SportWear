from django.core.exceptions import BadRequest
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from carts.models import CartItem
from store.models import Product
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
import requests
import json
import datetime
from django.db import transaction


@login_required
def payments(request):
    url = "https://a.khalti.com/api/v2/epayment/initiate/"
    return_url = request.POST.get('return_url')
    amount = request.POST.get('amount')
    user = request.user

    # Retrieve the recently placed order
    latest_order = Order.objects.filter(user=user, is_ordered=False).latest('id')

    # Set purchase_order_id to the order number
    purchase_order_id = latest_order.order_number

    payload = json.dumps({
        "return_url": return_url,
        "website_url": "http://127.0.0.1:8000/",
        "amount": amount,
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": "test",
        "customer_info": {
            "name": user.first_name,
            "email": user.email,
            "phone": user.phone_number
        }
    })

    headers = {
        'Authorization': 'key 3d81033b080d475c8b9911b83cbfa75f',
        'Content-Type': 'application/json',
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    new_res = json.loads(response.text)
    return redirect(new_res['payment_url'])


@login_required
def verifyKhalti(request, purchase_order_id=None, payment=None):
    url = "https://a.khalti.com/api/v2/epayment/lookup/"
    if request.method == 'GET':
        headers = {
            'Authorization': 'key 3d81033b080d475c8b9911b83cbfa75f',
            'Content-Type': 'application/json',
        }
        pidx = request.GET.get('pidx')
        data = json.dumps({
            'payment_id': pidx
        })
        res = requests.request('POST', url, headers=headers, data=data)

        new_res = json.loads(res.text)

        if new_res['status'] == 'Completed':
            # Update order status to mark it as completed
            Order.objects.filter(order_number=purchase_order_id).update(is_ordered=True)
        else:
            raise BadRequest("Payment verification failed")

        # Move the cart items to Order Product table
        cart_items = CartItem.objects.filter(user=request.user)

        for item in cart_items:
            orderproduct = OrderProduct.objects.create(
                order_id=purchase_order_id,
                user_id=request.user.id,
                product_id=item.product_id,
                quantity=item.quantity,
                product_price=item.product.price,
                ordered=True
            )
            product_variation = item.variations.all()
            orderproduct.variations.set(product_variation)

            # Reduce the quantity of the sold products
            product = Product.objects.get(id=item.product_id)
            product.stock -= item.quantity
            product.save()

        # Clear cart
        CartItem.objects.filter(user=request.user).delete()
        return redirect('home')
    else:
        raise BadRequest("Invalid request method")


@login_required
def place_order(request, total=0, quantity=0):
    current_user = request.user

    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            order = Order.objects.create(
                user=current_user,
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data['phone'],
                email=data['email'],
                address_line_1=data['address_line_1'],
                address_line_2=data['address_line_2'],
                country=data['country'],
                state=data['state'],
                city=data['city'],
                order_note=data['order_note'],
                order_total=grand_total,
                tax=tax,
                ip=request.META.get('REMOTE_ADDR')
            )

            # Generate order number
            current_date = datetime.date.today().strftime("%Y%m%d")
            order_number = current_date + str(order.id)
            order.order_number = order_number
            order.save()

            context = {
                'order': order,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total,
            }
            return render(request, 'orders/payments.html', context)
        else:
            return redirect('checkout')


@login_required
def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = sum([i.product_price * i.quantity for i in ordered_products])

        payment = Payment.objects.create(
            user=request.user,
            payment_id=transID,
            amount=order.order_total,
            status="Completed"  # Assuming payment is successful
        )

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')

