from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('inventory/', views.inventory, name='inventory'),
    path('pos/', views.pos, name='pos'),
    path('add-batch/', views.add_batch, name='add_batch'),
    path('reports/', views.reports, name='reports'),
    path('login/', views.custom_login, name='login'),   
    path('logout/', views.custom_logout, name='logout'), 
    path('receipt/<int:txn_id>/', views.receipt, name='receipt'),
    path('add-drug/', views.add_drug, name='add_drug'), 
    path('staff/', views.manage_staff, name='manage_staff'),
    path('add-staff/', views.add_staff, name='add_staff'),
    path('dispose/<int:batch_id>/', views.dispose_batch, name='dispose_batch'),
]