from django.urls import path

from commits.views import CommitList, CommitDetail

urlpatterns = [
    path('', CommitList.as_view(), name='commits'),
    path('f/<int:file_id>/', CommitList.as_view(), name='commit-by-file'),
    path('detail/<int:pk>/', CommitDetail.as_view(), name='commit-detail'),
]