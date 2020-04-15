[![Build Status](https://travis-ci.com/Yiling-J/django-cacheme.svg?branch=master)](https://travis-ci.com/Yiling-J/django-cacheme)
[![Build Status](https://codecov.io/gh/Yiling-J/django-cacheme/branch/master/graph/badge.svg)](https://codecov.io/gh/Yiling-J/django-cacheme)
# Django-Cacheme

Django-Cacheme is a memoized/cache package for Django based on [Cacheme](https://github.com/Yiling-J/cacheme).


## Features

Cacheme features: https://github.com/Yiling-J/cacheme

Django-Cacheme Extend Cacheme to support Django settings, and integrate Django model signals automatically.
Also provide an admin page to manage your cache.

## Getting started

`pip install django-cacheme`

Add 'django_cacheme' to your INSTALLED_APPS

Update your Django settings:
```
CACHEME = {
    'ENABLE_CACHE': True,
    'REDIS_CACHE_ALIAS': 'cacheme',  # your CACHES alias name in settings, optional, 'default' as default
    'REDIS_CACHE_PREFIX': 'MYCACHE:',  # cacheme key prefix, optional, 'CM:' as default
    'THUNDERING_HERD_RETRY_COUNT': 5,  # thundering herd retry count, if key missing, default 5
    'THUNDERING_HERD_RETRY_TIME': 20,  # thundering herd wait time(millisecond) between each retry, default 20
	'STALE': True  # Global setting for using stale, default True
}
```

Finally run migrate before use


## Features for Django

#### - Cacheme Decorator

Django-Cacheme add new parameters to cacheme decorator:

`invalid_models`/`invalid_m2m_models`: List, default []. Models and m2m models that will trigger the invalid
signal, every model must has an invalid_key property(can be a list), and m2m model need m2m keys(see Model part).
And when signal is called, all members in the model instance invalid key will be removed.

#### - Model property/attribute

To make invalid signal work, you need to define property for models that connect to signals in models.py.
As you can see in the example, a `cache_key` property is needed. And when invalid signal is triggered,
signal func will get this property value, add ':invalid' to it, and then invalid all keys store in this key.

```
class Book(models.Model):
    ...
	
    @property
    def cache_key(self):
        return "Book:%s" % self.id
```

This is enough for simple models, but for models include m2m field, we need some special rules. For example,
`Book` model has a m2m field to `User`, and if we do: `book.users.add(users)`, We have two update, first, book.users changed,
because a new user is add to this. Second, user.books also change, because this user has a new book. And on the other side,
if we do `user.books.add(books)`, also get two updates.
So if you take a look on [models.py](../master/tests/testapp/models.py), you will notice I add a `m2m_cache_keys` dict to through model,
that's because both `book.add()` and `user.add()` will trigger the [m2m invalid signal](https://docs.djangoproject.com/en/2.2/ref/signals/#m2m-changed), but the first one, signal `instance` will be book, and
`pk_set` will be users ids, and the second one, signal `instance` will be user, `pk_set` will be books ids. So the invalid keys is different
depend the `instance` in signal function.

```
Book.users.through.m2m_cache_keys = {

    # book is instance, so pk_set are user ids, used in signal book.users.add(users)
    'Book': lambda ids: ['User:%s:books' % id for id in ids],
	
    # user is instance, so pk_set are book ids, used in signal user.books.add(books)
    'TestUser': lambda ids: ['Book:%s:users' % id for id in ids],
    
}
```

#### - Model based Node

Django-Cacheme add a new node class called ModelInvalidNode, this invalid node class can handle model signal
automatically. When using ModelInvalidNode, no need to add property/attribute to model any more.

For model without m2m, just add `model = YourModel` to invalid node meta attributes. This will connect
`post_save/delete` signals automatically. You can pass instance directly to ModelInvalidNode,
`invalid_nodes.InvalidUserNode(instance=self.user)`, ModelInvalidNode will find value for all fields from this
instance.

For model with m2m, add `model = YourM2MModel` and `m2m = True` to class meta. You can't use instance for M2MNode. Instead, add the fk field in m2m model as fields in your invalid node. For example, `UserBook` model has 2 foreign keys `user` and `book`, you can use either `InvalidUserBookNode(user=self.user)` or `InvalidUserBookNode(book=self.book)`, first one will create invalid key: `user:{user_id}:book:all`, second one will create invalid key `user:all:book:{book_id}`

Example:

```
from django_cacheme import nodes


class InvalidUserNode(nodes.ModelInvalidNode):
    id = nodes.Field()

    def key(self):
        return 'user:%s' % self.id

    class Meta:
        model = models.User
		
		
class UserNode(nodes.Node):
    user = nodes.Field()

    def key(self):
        return 'user:%s' % self.user.id

    def invalid_nodes(self):
        return [
            invalid_nodes.InvalidUserNode(instance=self.user)
        ]
		

# create invalidation manually

# get fields from instance automatically
InvalidUserNode.objects.invalid(instance=user)
# or using field explictly
InvalidUserNode.objects.invalid(id=user.id)

```

Example M2M:

```
from django_cacheme import nodes


class InvalidUserBookNode(nodes.ModelInvalidNode):
    user = nodes.Field()
    book = nodes.Field()

    def key(self):
        return 'user:%s:book:%s' % (self.testuser, self.book)

    class Meta:
        model = models.TestUser.books.through
        m2m = True


class UserBookNode(nodes.Node):
    user = nodes.Field()

    def key(self):
        return 'user:%s' % self.user.id

    def invalid_nodes(self):
        return [
            invalid_nodes.InvalidUserBookNode(user=self.user)
        ]
		

# create invalidation manually
InvalidUserBookNode.objects.invalid(user=user)
InvalidUserBookNode.objects.invalid(book=book)


```
