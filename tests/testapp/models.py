from django.db import models


class TestUser(models.Model):
    name = models.CharField(max_length=30)

    @property
    def cache_key(self):
        return "User:%s" % self.id


class Book(models.Model):
    name = models.CharField(max_length=30)
    users = models.ManyToManyField(TestUser, related_name='books')

    @property
    def cache_key(self):
        return "Book:%s" % self.id


Book.users.through.m2m_cache_keys = {
    'Book': lambda ids: ['User:%s:books' % id for id in ids],
    'TestUser': lambda ids: ['Book:%s:users' % id for id in ids],
}
