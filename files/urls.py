from django.urls import path

from files.views import FileList, FileView

urlpatterns = [
    path('', FileList.as_view(), name='files'),
    path('detail/<int:pk>/', FileView.as_view(), name='file-detail-view'),
]
