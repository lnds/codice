from django.urls import path

from files.views import FileList

urlpatterns = [
    path('', FileList.as_view(), name='files'),
]
