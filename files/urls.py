from django.urls import path

from files.views import FileList, FileView

urlpatterns = [
    path('', FileList.as_view(), name='files'),
    path('list/', FileList.as_view(), name='files'),
    path('list/r/<int:repo_id>/', FileList.as_view(), name='file-list-repo'),
    path('detail/<int:pk>/', FileView.as_view(), name='file-detail-view'),
]
