#!/usr/bin/env python
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from os import path

# Give feedback on used versions
sys.stderr.write('Using Python version {0} from {1}\n'.format(sys.version[:5], sys.executable))
sys.stderr.write('Using Django version {0} from {1}\n'.format(
    django.get_version(),
    path.dirname(path.abspath(django.__file__)))
)

if not settings.configured:
    module_root = path.dirname(path.realpath(__file__))
    sys.path.insert(0, path.join(module_root, 'example'))

    settings.configure(
        DEBUG = False,  # will be False anyway by DjangoTestRunner.

        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': 'redis://localhost:6379/0',
            },
            'cacheme': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': 'redis://localhost:6379/12',
            },
        },
        CACHEME = {
            'ENABLE_CACHE': True,
            'REDIS_CACHE_TEST_DB': 12,
            'REDIS_CACHE_ALIAS': 'cacheme',
            'REDIS_CACHE_PREFIX': 'TEST:'
        },
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS = (
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sites',
            'django.contrib.admin',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django_cacheme',
            'tests.testapp'
        ),
        TEMPLATES = [
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': (),
                'OPTIONS': {
                    'loaders': (
                        'django.template.loaders.filesystem.Loader',
                        'django.template.loaders.app_directories.Loader',
                    ),
                    'context_processors': (
                        'django.template.context_processors.debug',
                        'django.template.context_processors.i18n',
                        'django.template.context_processors.media',
                        'django.template.context_processors.request',
                        'django.template.context_processors.static',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages'
                    ),
                },
            },
        ],
        MIDDLEWARE = (
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ),

        TEST_RUNNER = 'django.test.runner.DiscoverRunner'

        )

DEFAULT_TEST_APPS = [
    'tests.testapp',
]


def runtests():
    other_args = list(filter(lambda arg: arg.startswith('-'), sys.argv[1:]))
    test_apps = list(filter(lambda arg: not arg.startswith('-'), sys.argv[1:])) or DEFAULT_TEST_APPS
    argv = sys.argv[:1] + ['test', '--traceback'] + other_args + test_apps
    execute_from_command_line(argv)


if __name__ == '__main__':
    runtests()
