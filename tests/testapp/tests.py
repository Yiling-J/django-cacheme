import pickle
import time
import datetime

import redis
from unittest.mock import MagicMock
from django.conf import settings
from django.test import TestCase
from django_redis import get_redis_connection

from .models import TestUser, Book
from django_cacheme import cacheme
from django_cacheme.models import Invalidation

from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django_cacheme.admin import InvalidationAdmin

r = redis.Redis()


hit = MagicMock()
miss = MagicMock()


class BaseTestCase(TestCase):
    def tearDown(self):
        connection = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        connection.flushdb(settings.CACHEME['REDIS_CACHE_TEST_DB'])


class CacheTestCase(BaseTestCase):

    @cacheme(
        key=lambda c: "Test:123",
        invalid_keys=lambda c: ["User:%s" % c.user1.id],
        invalid_models=[TestUser]
    )
    def cache_test_func1(self, user1, user2):
        return {'results': [{'id': user1.id}, {'id': user2.id}], 'check': self.check}

    @cacheme(
        key=lambda c: str(c.self.pp + c.a + c.args[0] + c.kwargs['ff']),
    )
    def cache_bind_func(self, a, *args, **kwargs):
        return self.pp + a + args[0] + kwargs['ff']

    def test_cache_simple(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')
        self.check = 1

        expect = {'results': [{'id': user1.id}, {'id': user2.id}], 'check': 1}

        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:123', 'base')
        self.assertEqual(pickle.loads(result), expect)

        self.check = 2

        # still using cache, so old value
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        # user1 signal triggered, so cache invalid now
        user1.name += 'cc'
        user1.save()

        # lazy invalid, so if we get value directly, still old value
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:123', 'base')
        self.assertEqual(pickle.loads(result), expect)
        deletes = conn.smembers(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'delete')
        self.assertTrue(b'TEST:Test:123' in deletes)

        expect['check'] = 2
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        # no signal for user2, still using cache
        self.check = 3
        user2.name += 'cc'
        user2.save()
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

    def test_cache_arguments_bind(self):
        self.pp = 3
        result = self.cache_bind_func(1, 2, ff=14, qq=5)
        self.assertEqual(result, 20)
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + '20', 'base')
        self.assertEqual(pickle.loads(result), 20)

    @cacheme(
        key=lambda c: "Test:123",
        hit=hit,
        miss=miss
    )
    def cache_test_func_hit_miss(self):
        return 'test'

    def test_cache_hit_miss(self):
        self.cache_test_func_hit_miss()
        self.assertEqual(miss.call_count, 1)
        hit.assert_not_called()
        self.cache_test_func_hit_miss()
        self.assertEqual(miss.call_count, 1)
        self.assertEqual(hit.call_count, 1)

    @cacheme(
        key=lambda c: "Test:m2m",
        invalid_keys=lambda c: ["Book:%s:users" % c.book.id],
        invalid_m2m_models=[Book.users.through]
    )
    def cache_m2m_left_func(self, book):
        return {'users': [u.id for u in book.users.all()]}

    @cacheme(
        key=lambda c: "Test:m2m:pks",
        invalid_keys=lambda c: ["User:%s:books" % c.user.id],
        invalid_m2m_models=[Book.users.through]
    )
    def cache_m2m_right_func(self, user):
        return {'books': [b.id for b in user.books.all()]}

    def test_m2m_cache_left(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')

        book = Book.objects.create(name='book')
        book.users.add(user1, user2)
        result = self.cache_m2m_left_func(book)
        self.assertEqual(result, {'users': [user1.id, user2.id]})
        result_user = self.cache_m2m_right_func(user1)
        self.assertEqual(result_user, {'books': [book.id]})
        book.users.remove(user1)
        result = self.cache_m2m_left_func(book)
        self.assertEqual(result, {'users': [user2.id]})
        result_user = self.cache_m2m_right_func(user1)
        self.assertEqual(result_user, {'books': []})

    def test_m2m_cache_right(self):
        user = TestUser.objects.create(name='test1')

        book1 = Book.objects.create(name='book')
        book2 = Book.objects.create(name='book2')
        user.books.add(book1, book2)
        result = self.cache_m2m_left_func(book1)
        self.assertEqual(result, {'users': [user.id]})
        result_user = self.cache_m2m_right_func(user)
        self.assertEqual(result_user, {'books': [book1.id, book2.id]})
        user.books.remove(book1)
        result = self.cache_m2m_left_func(book1)
        self.assertEqual(result, {'users': []})
        result_user = self.cache_m2m_right_func(user)
        self.assertEqual(result_user, {'books': [book2.id]})

    @cacheme(
        key=lambda c: "INST:1"
    )
    def cache_inst_1(self):
        return 'test'

    @cacheme(
        key=lambda c: "INST:2",
        tag='test_instance_sec'
    )
    def cache_inst_2(self):
        return 'test'

    @cacheme(
        key=lambda c: "INST:3",
        tag='three'
    )
    def cache_inst_3(self):
        return 'test'

    def test_tags(self):
        self.cache_inst_1()
        self.cache_inst_2()
        self.cache_inst_3()
        self.assertEqual(cacheme.tags['cache_inst_1'].invalid_all(), 1)
        self.assertEqual(cacheme.tags['test_instance_sec'].invalid_all(), 1)
        self.assertEqual(cacheme.tags['three'].invalid_all(), 1)
        cacheme.tags['three'].invalid_all()
        self.assertEqual(cacheme.tags['three'].invalid_all(), 0)

    def test_invalidation_model(self):
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        conn.set('TEST:PATTERN:1', 1)
        conn.set('TEST:PATTERN:2', 2)
        conn.set('TEST:ANOTHER:3', 3)

        self.assertEqual(conn.get('TEST:PATTERN:1'), b'1')
        self.assertEqual(conn.get('TEST:PATTERN:2'), b'2')
        self.assertEqual(conn.get('TEST:ANOTHER:3'), b'3')

        Invalidation.objects.create(pattern='TEST:PATTERN*')

        self.assertEqual(conn.get('TEST:PATTERN:1'), None)
        self.assertEqual(conn.get('TEST:PATTERN:2'), None)
        self.assertEqual(conn.get('TEST:ANOTHER:3'), b'3')

    @cacheme(
        key=lambda c: "CACHE:SKIP:1",
        tag='three',
        skip=True
    )
    def cache_skip_bool(self, data):
        return {'result': data['test']}

    @cacheme(
        key=lambda c: "CACHE:SKIP:2",
        tag='three',
        skip=lambda c: 'skip' in c.data
    )
    def cache_skip_callable(self, data):
        return {'result': data['test']}

    def test_skip_cache(self):
        result = self.cache_skip_bool({'test': 1})
        self.assertEqual(result['result'], 1)

        result = self.cache_skip_bool({'test': 2})
        self.assertEqual(result['result'], 2)

        result = self.cache_skip_callable({'test': 3})
        self.assertEqual(result['result'], 3)

        result = self.cache_skip_callable({'test': 4, 'skip': True})
        self.assertEqual(result['result'], 4)

        result = self.cache_skip_callable({'test': 5})
        self.assertEqual(result['result'], 5)

        result = self.cache_skip_callable({'test': 6})
        self.assertEqual(result['result'], 6)

    @cacheme(
        key=lambda c: "CACHE:TO",
        timeout=1
    )
    def cache_timeout(self, n):
        return n

    @cacheme(
        key=lambda c: "CACHE:TO2",
        timeout=1
    )
    def cache_timeout2(self, n):
        return n

    @cacheme(
        key=lambda c: "CACHE:TO3",
        timeout=3
    )
    def cache_timeout3(self, n):
        return n

    def test_time_out(self):
        self.assertEqual(self.cache_timeout(1), 1)
        self.assertEqual(self.cache_timeout(2), 1)
        self.assertEqual(self.cache_timeout2(1), 1)
        self.assertEqual(self.cache_timeout2(2), 1)
        time.sleep(1.02)
        self.assertEqual(self.cache_timeout(2), 2)
        self.assertEqual(self.cache_timeout2(2), 2)
        self.assertEqual(self.cache_timeout3(1), 1)
        self.assertEqual(self.cache_timeout2(3), 2)
        time.sleep(1.02)
        self.assertEqual(self.cache_timeout2(3), 3)
        self.assertEqual(self.cache_timeout3(3), 1)

    @cacheme(
        key=lambda c: "Test:123",
        invalid_keys=lambda c: ["User:%s" % c.user1.id],
        invalid_models=[TestUser],
        timeout=1
    )
    def cache_timeout_signal(self, user1, user2):
        return {'results': [{'id': user1.id}, {'id': user2.id}], 'check': self.check}

    def test_timeout_with_signal(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')
        self.check = 1

        expect = {'results': [{'id': user1.id}, {'id': user2.id}], 'check': 1}

        result = self.cache_timeout_signal(user1, user2)
        self.assertEqual(result, expect)

        self.check = 2

        user1.name += 'cc'
        user1.save()

        expect['check'] = 2
        result = self.cache_timeout_signal(user1, user2)
        self.assertEqual(result, expect)

        self.check = 3
        time.sleep(1.04)

        expect['check'] = 3
        result = self.cache_timeout_signal(user1, user2)
        self.assertEqual(result, expect)

    @cacheme(
        key=lambda c: "CACHE:TH",
    )
    def cache_th(self, n):
        return n

    def test_key_missing(self):
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        conn.sadd('TEST:progress', 'TEST:CACHE:TH')
        start = datetime.datetime.now()
        result = self.cache_th(12)
        end = datetime.datetime.now()
        delta = (end - start).total_seconds() * 1000
        self.assertEqual(result, 12)
        self.assertTrue(delta > 50)

        conn.sadd('TEST:progress', 'TEST:CACHE:TH')
        start = datetime.datetime.now()
        result = self.cache_th(15)
        end = datetime.datetime.now()
        self.assertEqual(result, 12)
        self.assertTrue(delta > 50)

    @cacheme(
        key=lambda c: "CACHE:RESULT",
        invalid_keys=lambda c: ["Book:%s" % id for id in c.cacheme_result],
        invalid_models=[Book]

    )
    def cache_result(self, book):
        return [book.id]

    def test_invalid_cacheme_result(self):
        book1 = Book.objects.create(name='b1')
        r = self.cache_result(book1)
        self.assertEqual(r, [book1.id])

        book2 = Book.objects.create(name='b2')
        r = self.cache_result(book2)
        self.assertEqual(r, [book1.id])

        book1.name = 'bn'
        book1.save()

        r = self.cache_result(book2)
        self.assertEqual(r, [book2.id])


class AdminTestCase(BaseTestCase):

    @cacheme(
        key=lambda c: 'testme',
        tag='test'
    )
    def cache_test(self):
        return 'test'

    def test_admin(self):
        admin = InvalidationAdmin(model=Invalidation, admin_site=AdminSite())
        request = RequestFactory()
        request.user = User.objects.create(username='test_admin')

        form = admin.get_form(request=request)
        self.assertEqual(form.declared_fields['invalid_tags'].initial, None)
        self.assertEqual(form.declared_fields['invalid_tags'].disabled, False)

        self.cache_test()
        obj = Invalidation.objects.create(tags='test')
        form = admin.get_form(request=request, obj=obj)

        self.assertEqual(form.declared_fields['invalid_tags'].initial, ['test'])
        self.assertEqual(form.declared_fields['invalid_tags'].disabled, True)

        obj2 = Invalidation(id=999)
        form = admin.get_form(request=request, obj=None)({'pattern': 'aaa', 'invalid_tags': ['test']})
        self.assertTrue(form.is_valid())
        admin.save_model(request, obj2, form, False)
        self.assertEqual(Invalidation.objects.get(id=999).tags, 'test')
