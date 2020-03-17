from django.urls import path

from .views import DeveloperList

urlpatterns = [
    path('', DeveloperList.as_view(), name='devs'),
]