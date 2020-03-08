from django.db import models

from developers.models import Developer
from repos.models import Branch, Repository


class Commit(models.Model):
    hexsha = models.CharField(max_length=40)
    date = models.DateTimeField()
    message = models.TextField(null=True, blank=True)
    lines = models.IntegerField()
    insertions = models.IntegerField()
    deletions = models.IntegerField()
    net = models.IntegerField()
    is_merge = models.BooleanField(default=False)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    original_author = models.ForeignKey(Developer, related_name='original_author',
                                        related_query_name='original_authors',
                                        on_delete=models.SET_NULL,
                                        default=None,
                                        null=True)

    class Meta:
        db_table = 'codice_commit'

    def __str__(self):
        return "{} @ {}: {}".format(self.hexsha[-6:], self.date,  self.message[:20])
