import time
import pickle
import datetime
import logging

from functools import wraps
from django.db.models.signals import m2m_changed, post_delete, post_save
from django_redis import get_redis_connection
from inspect import _signature_from_function, Signature

from .utils import split_key, invalid_cache, flat_list, CACHEME, hget_with_ttl, hset_with_ttl


logger = logging.getLogger('cacheme')

cacheme_tags = dict()


class CacheMe(object):
    key_prefix = CACHEME.REDIS_CACHE_PREFIX
    deleted = key_prefix + 'delete'

    def __init__(self, key, invalid_keys=None, invalid_models=(), invalid_m2m_models=(), hit=None, miss=None, tag=None, skip=False, timeout=None):
        if not CACHEME.ENABLE_CACHE:
            return
        self.key = key
        self.invalid_keys = invalid_keys
        self.invalid_models = invalid_models
        self.invalid_m2m_models = invalid_m2m_models
        self.hit = hit
        self.miss = miss
        self.tag = tag
        self.skip = skip
        self.timeout = timeout
        self.progress_key = self.key_prefix + 'progress'

        self.conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
        self.link()

    def __call__(self, func):

        self.function = func

        self.tag = self.tag or func.__name__
        cacheme_tags[self.tag] = self

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHEME.ENABLE_CACHE:
                return self.function(*args, **kwargs)

            # bind args and kwargs to true function params
            signature = _signature_from_function(Signature, func)
            bind = signature.bind(*args, **kwargs)
            bind.apply_defaults()

            # then apply args and kwargs to a container,
            # in this way, we can have clear lambda with just one
            # argument, and access what we need from this container
            self.container = type('Container', (), bind.arguments)

            if callable(self.skip) and self.skip(self.container):
                return self.function(*args, **kwargs)
            elif self.skip:
                return self.function(*args, **kwargs)

            key = self.key_prefix + self.key(self.container)

            if self.timeout:
                result = self.get_key(key)

            if self.conn.srem(self.deleted, key):
                result = self.function(*args, **kwargs)
                self.set_result(key, result)
                self.container.cacheme_result = result
                self.add_to_invalid_list(key, args, kwargs)
                return result

            if self.timeout is None:
                result = self.get_key(key)

            if result is None:

                if self.add_to_progress(key) == 0:  # already in progress
                    for i in range(CACHEME.THUNDERING_HERD_RETRY_COUNT):
                        time.sleep(CACHEME.THUNDERING_HERD_RETRY_TIME/1000)
                        result = self.get_key(key)
                        if result:
                            return result

                result = self.get_result_from_func(args, kwargs, key)
                self.set_result(key, result)
                self.remove_from_progress(key)
                self.container.cacheme_result = result
                self.add_to_invalid_list(key, args, kwargs)
            else:
                if self.hit:
                    self.hit(key, result, self.container)
                result = result

            self.container = None
            return result

        return wrapper

    @property
    def keys(self):
        return self.conn.smembers(CACHEME.REDIS_CACHE_PREFIX + self.tag)

    @keys.setter
    def keys(self, val):
        self.conn.sadd(CACHEME.REDIS_CACHE_PREFIX + self.tag, val)

    def invalid_all(self):
        keys = self.keys
        if not keys:
            return
        self.conn.sadd(self.deleted, *keys)
        self.conn.unlink(CACHEME.REDIS_CACHE_PREFIX + self.tag)

    def get_result_from_func(self, args, kwargs, key):
        if self.miss:
            self.miss(key, self.container)

        start = datetime.datetime.now()
        result = self.function(*args, **kwargs)
        end = datetime.datetime.now()
        delta = (end - start).total_seconds() * 1000
        logger.debug(
            '[CACHEME FUNC LOG] key: "%s", time: %s ms' % (key, delta)
        )
        return result

    def set_result(self, key, result):
        self.set_key(key, result)

    def get_key(self, key):
        key, field = split_key(key)
        if self.timeout:
            result = hget_with_ttl(key, field)
        else:
            result = self.conn.hget(key, field)

        if result:
            result = pickle.loads(result)
        return result

    def set_key(self, key, value):
        self.keys = key
        value = pickle.dumps(value)
        key, field = split_key(key)
        if self.timeout:
            hset_with_ttl(key, field, value, self.timeout)
        else:
            self.conn.hset(key, field, value)

    def push_key(self, key, value):
        return self.conn.sadd(key, value)

    def add_to_invalid_list(self, key, args, kwargs):
        invalid_keys = self.invalid_keys

        if not invalid_keys:
            return

        invalid_keys = invalid_keys(self.container)
        invalid_keys = flat_list(invalid_keys)
        for invalid_key in set(filter(lambda x: x is not None, invalid_keys)):
            invalid_key += ':invalid'
            invalid_key = self.key_prefix + invalid_key
            self.push_key(invalid_key, key)

    def link(self):
        models = self.invalid_models
        m2m_models = self.invalid_m2m_models

        for model in models:
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)

        for model in m2m_models:
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)
            m2m_changed.connect(invalid_cache, model)

    def remove_from_progress(self, key):
        self.conn.srem(self.progress_key, key)

    def add_to_progress(self, key):
        return self.conn.sadd(self.progress_key, key)
