from django.contrib import admin

from authentication.models import User


class CustomUserAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, CustomUserAdmin)