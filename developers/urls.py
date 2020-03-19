from django.urls import path

from .views import DeveloperList

urlpatterns = [
    path('', DeveloperList.as_view(), name='devs'),
    path('r/<int:repo_id>/', DeveloperList.as_view(), name='repo-devs-list'),
]