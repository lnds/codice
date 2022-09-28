from django.urls import path

from .views import DeveloperList, DeveloperProfile, DeveloperUpdate, DeveloperDashboard

urlpatterns = [
    path('', DeveloperList.as_view(), name='devs'),
    path('dashboard', DeveloperDashboard.as_view(), name='devs-dashboard'),
    path('dashboard/r/<int:repo_id>', DeveloperDashboard.as_view(), name='devs-dashboard-repo'),
    path('r/<int:repo_id>/', DeveloperList.as_view(), name='repo-devs-list'),
    path('profile/<int:pk>/', DeveloperProfile.as_view(), name='full-developer-profile'),
    path('profile/<int:pk>/update/', DeveloperUpdate.as_view(), name='full-developer-update'),
]