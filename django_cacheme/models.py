from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .utils import CACHEME
from .cache_model import CacheMe as cacheme


def default_pattern():
    return CACHEME.REDIS_CACHE_PREFIX + '*'


class Invalidation(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    pattern = models.CharField(max_length=200, default=default_pattern)
    created = models.DateTimeField(default=timezone.now)
    tags = models.CharField(max_length=5000, default='')

    def __str__(self):
        return self.pattern

    def save(self, *args, **kwargs):
        if not self.pk:
            cacheme.create_invalidation(pattern=self.pattern)
            tags = self.tags.split(',')
            for tag in tags:
                if tag:
                    cacheme.tags[tag].objects.invalid()
        super().save(*args, **kwargs)
