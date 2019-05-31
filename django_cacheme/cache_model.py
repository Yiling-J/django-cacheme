import pickle
import datetime
import logging

from django.db.models.signals import m2m_changed, post_delete, post_save
from django_redis import get_redis_connection
from inspect import _signature_from_function, Signature

from .utils import split_key, invalid_cache, flat_list, CACHEME


logger = logging.getLogger('cacheme')


class CacheMe(object):
    key_prefix = CACHEME.REDIS_CACHE_PREFIX
    deleted = key_prefix + ':delete'

    def __init__(self, key, invalid_keys=None, invalid_models=[], invalid_m2m_models=[], override=None):
        self.key = key
        self.invalid_keys = invalid_keys
        self.invalid_models = invalid_models
        self.invalid_m2m_models = invalid_m2m_models
        self.override = override

        self.conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
        self.link()

    def __call__(self, func):

        self.function = func

        def wrapper(*args, **kwargs):
            if not CACHEME.ENABLE_CACHE:
                return self.function(*args, **kwargs)

            # bind args and kwargs to true function params
            signature = _signature_from_function(Signature, func)
            bind = signature.bind(*args, **kwargs)
            bind.apply_defaults()

            container = type('Container', (), bind.arguments)

            key = self.key_prefix + self.key(container)

            if self.conn.srem(self.deleted, key):
                result = self.function(*args, **kwargs)
                self.set_result(container, key, result)
                self.add_to_invalid_list(key, container, args, kwargs)
                return result

            result = self.get_key(key)

            if result is None:
                result = self.get_result_from_func(args, kwargs, key)
                self.set_result(container, key, result)
                self.add_to_invalid_list(key, container, args, kwargs)
            elif type(result) != int and 'redis_key' in result:
                result = self.get_key(result['redis_key'])
                if result is None:
                    result = self.get_result_from_func(args, kwargs, key)
                    self.set_key(self.get_key(result['redis_key']), result)
            else:
                result = result

            return result

        return wrapper

    def get_result_from_func(self, args, kwargs, key):
        start = datetime.datetime.now()
        result = self.function(*args, **kwargs)
        end = datetime.datetime.now()
        delta = (end - start).total_seconds() * 1000
        logger.debug(
            '[CACHEME FUNC LOG] key: "%s", time: %s ms' % (key, delta)
        )
        return result

    def set_result(self, container, key, result):
        if self.override and self.override(container):
            okey = self.override(container)
            okey = CACHEME.REDIS_CACHE_PREFIX + okey
            self.set_key(key, {'redis_key': okey})
            self.set_key(okey, result)
        else:
            self.set_key(key, result)

    def get_key(self, key):
        key, field = split_key(key)
        result = self.conn.hget(key, field)

        if result:
            result = pickle.loads(result)
        return result

    def set_key(self, key, value):
        value = pickle.dumps(value)
        key, field = split_key(key)
        return self.conn.hset(key, field, value)

    def push_key(self, key, value):
        return self.conn.sadd(key, value)

    def add_to_invalid_list(self, key, container, args, kwargs):
        invalid_keys = self.invalid_keys

        if not invalid_keys:
            return

        invalid_keys = invalid_keys(container)
        invalid_keys = flat_list(invalid_keys)
        for invalid_key in set(filter(lambda x: x is not None, invalid_keys)):
            invalid_key += ':invalid'
            invalid_key = self.key_prefix + invalid_key
            self.push_key(invalid_key, key)

    def link(self):
        models = self.invalid_models
        m2m_models = self.invalid_m2m_models

        if not models:
            return

        for model in models:
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)

        if not m2m_models:
            return

        for model in m2m_models:
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)
            m2m_changed.connect(invalid_cache, model)
