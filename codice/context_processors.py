from django.conf import settings

def codice_version(request):
    """shows codice version on templates"""
    return {'CODICE_VERSION': settings.CODICE_VERSION}
