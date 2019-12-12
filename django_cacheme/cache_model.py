from django.db.models.signals import m2m_changed, post_delete, post_save
from django_redis import get_redis_connection

from .utils import invalid_cache, CACHEME, CACHEME_DICT

from cacheme import cacheme as BaseCacheMe


class CacheMe(BaseCacheMe):

    def collect_sources(self):
        models = self.kwargs.get('invalid_models', [])
        m2m_models = self.kwargs.get('invalid_m2m_models', [])
        results = set()

        for model in models:
            model.signal_type = 'ONE'
            results.add(model)

        for model in m2m_models:
            model.signal_type = 'M2M'
            results.add(model)
        return results

    def connect(self, model):
        if model.signal_type == 'ONE':
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)

        if model.signal_type == 'M2M':
            post_save.connect(invalid_cache, model)
            post_delete.connect(invalid_cache, model)
            m2m_changed.connect(invalid_cache, model)


redis_connection = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
CacheMe.set_connection(redis_connection)
CacheMe.update_settings(CACHEME_DICT)
