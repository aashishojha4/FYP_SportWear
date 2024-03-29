from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from category.models import Category

from .models import Product


# Create your views here.
def store(request, category_slug=None):
    categories = None
    products = None
    product_count = 0  # Initialize product count

    if category_slug is not None:
        categories = get_object_or_404(Category, slug=category_slug)  # Updated model name
        products = Product.objects.filter(category=categories, is_available=True)
        product_count = products.count()
    else:
        products = Product.objects.filter(is_available=True)
        product_count = products.count()

    context = {
        'products': products,
        'product_count': product_count
    }
    return render(request, 'store/store.html', context)


def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
    except Product.DoesNotExist:
        # Handle the case where the product does not exist
        return HttpResponse("Product not found", status=404)
    except Exception as e:
        # Handle other exceptions
        return HttpResponse("An error occurred", status=500)

    context = {
        'single_product': single_product
    }

    return render(request, 'store/product_detail.html', context)
