from django.urls import path
from shop.views import shop_featured_list, shop_list, shop_map_list, shop_detail, global_search

urlpatterns = [
    # List
    path('global-search/', global_search, name='shop-featured-list'),
    path('shop-featured-list/', shop_featured_list, name='shop-featured-list'),
    path('shop-list/', shop_list, name='shop-list'),
    path('shop-map-list/', shop_map_list, name='shop-map-list'),
    # Detail
    path('shop-detail/<int:pk>/', shop_detail, name='shop-detail'),
]
