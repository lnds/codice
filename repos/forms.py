from django import forms

from repos.models import Repository


class RepositoryForm(forms.ModelForm):
    class Meta:
        model = Repository
        fields = ['name', 'url', 'username', 'password', 'branches_to_track', 'default_branch', 'public']