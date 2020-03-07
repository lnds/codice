from django.urls import path

from repos.views import RepositoryList, RepositoryCreate, RepositoryDetail, RepositoryDelete

urlpatterns = [
    path('', RepositoryList.as_view(), name='repos'),
    path('detail/<int:pk>/', RepositoryDetail.as_view(), name='repository-detail'),
    path('add/', RepositoryCreate.as_view(), name='repository-add'),
    path('delete/<int:pk>/', RepositoryDelete.as_view(), name='repository-delete'),
]
