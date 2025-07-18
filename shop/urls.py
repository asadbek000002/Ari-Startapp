from django.urls import path

from shop.views import (shop_featured_list, shop_list_by_role, shop_map_list, shop_detail,
                        global_search, shop_role_list, ShopRegistrationView, advertising_list, SHopFeedbackCreateView)

urlpatterns = [
    path('register/', ShopRegistrationView.as_view(), name='shop-register'),

    # List
    path('global-search/', global_search, name='search'),

    path('advertising/', advertising_list, name='advertising-list'),

    path('shop-role-list/', shop_role_list, name='shop-role-list'),
    path('shop-featured-list/', shop_featured_list, name='shop-featured-list'),
    path('shop-list/<int:role_id>/', shop_list_by_role, name='shop-list'),
    path('shop-map-list/<int:role_id>/', shop_map_list, name='shop-map-list'),
    # Detail
    path('shop-detail/<int:pk>/', shop_detail, name='shop-detail'),
    path('shops/<int:shop_id>/feedback/', SHopFeedbackCreateView.as_view(), name='shop-feedback-create')

]
