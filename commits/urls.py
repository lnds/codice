from django.urls import path

from .views import CommitList

urlpatterns = [
    path('', CommitList.as_view(), name='commits'),
]