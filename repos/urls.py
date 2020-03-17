from django.urls import path

from repos.views import RepositoryList, RepositoryCreate, RepositoryDetail, RepositoryDelete, repository_hotspots_json

urlpatterns = [
    path('', RepositoryList.as_view(), name='repos'),
    path('detail/<int:pk>/', RepositoryDetail.as_view(), name='repository-detail'),
    path('add/', RepositoryCreate.as_view(), name='repository-add'),
    path('delete/<int:pk>/', RepositoryDelete.as_view(), name='repository-delete'),
    path('detail/<int:pk>/<int:branch_id>/hotspots.json', repository_hotspots_json),
]
