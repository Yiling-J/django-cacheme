from django_cacheme import nodes
from . import models


class InvalidUserNode(nodes.ModelInvalidNode):
    id = nodes.Field()

    def key(self):
        return 'user:%s' % self.id

    class Meta:
        model = models.TestUser


class InvalidBookNode(nodes.ModelInvalidNode):
    id = nodes.Field()

    def key(self):
        return 'book:%s' % self.id

    class Meta:
        model = models.Book


class InvalidUserBookNode(nodes.ModelInvalidNode):
    testuser = nodes.Field()
    book = nodes.Field()

    def key(self):
        return 'user:%s:book:%s' % (self.testuser, self.book)

    class Meta:
        model = models.TestUser.books.through
        m2m = True
