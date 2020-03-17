from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('password_reset_done/',
         auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html'),
         name='password_reset_done'),
    path('recover-password/', auth_views.PasswordResetView.as_view(template_name='auth/recover_password.html')
         ,name='recover-password'),
    path('reset/<str:uidb64>/<str:token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name = 'auth/password_reset.html'),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html'),
         name='password_reset_complete')
]