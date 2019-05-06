from django.conf import settings
from django_redis import get_redis_connection


CACHEME = {
    'REDIS_CACHE_PREFIX': 'CM',  # key prefix for cache
}

CACHEME.update(getattr(settings, 'CACHEME', {}))
CACHEME = type('CACHEME', (), CACHEME)


def split_key(string):
    lg = b'>' if type(string) == bytes else '>'
    if lg in string:
        return string.split(lg)[:2]
    return [string, 'base']


def invalid_cache(sender, instance, created=False, **kwargs):
    # for manytomany pre signal, do nothing
    m2m = False
    if 'pre_' in kwargs.get('action', ''):
        return
    if kwargs.get('action', False):
        m2m = True

    if CACHEME.ENABLE_CACHE and instance.cache_key:
        conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
        keys = instance.cache_key
        if type(instance.cache_key) == str:
            keys = [keys]
        for key in keys:
            if m2m and sender.suffix:
                key = key + ':' + sender.suffix
            key = CACHEME.REDIS_CACHE_PREFIX + key + ':invalid'
            invalid_keys = conn.smembers(key)
            if invalid_keys:
                for key in invalid_keys:
                    ikey, field = split_key(key)
                    conn.hdel(ikey, field)


def flat_list(li):
    if type(li) not in (list, tuple, set):
        li = [li]

    result = []
    for e in li:
        if type(e) in (list, tuple, set):
            result += flat_list(e)
        else:
            result.append(e)
    return result
