from django_cacheme import nodes
from tests.testapp import invalid_nodes


class TestNodeUser(nodes.Node):
    user = nodes.Field()

    def key(self):
        return 'user:%s' % self.user.id

    def invalid_nodes(self):
        return [
            invalid_nodes.InvalidUserNode(instance=self.user)
        ]


class M2MTestNodeUser(nodes.Node):
    user = nodes.Field()

    def key(self):
        return 'user:%s' % self.user.id

    def invalid_nodes(self):
        return [
            invalid_nodes.InvalidUserBookNode(testuser=self.user)
        ]


class M2MTestNodeBook(nodes.Node):
    book = nodes.Field()

    def key(self):
        return self.book.id

    def invalid_nodes(self):
        return [
            invalid_nodes.InvalidUserBookNode(book=self.book)
        ]
