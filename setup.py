from setuptools import setup

description = 'Django-Cacheme is a memoized decorator for Django using redis'


setup(
    name="django-cacheme",
    url="https://github.com/Yiling-J/django-cacheme",
    author="Yiling",
    author_email="njjyl723@gmail.com",
    license="BSD-3-Clause",
    version='v0.1.3',
    packages=[
        "django_cacheme",
    ],
    description=description,
    python_requires=">=3.5",
    install_requires=[
        "cacheme>=0.1.1"
        "django_redis>=4.10.0",
    ],
    zip_safe=False,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 1.11",
        "Framework :: Django :: 2.0",
        "Framework :: Django :: 2.1",
        "Framework :: Django :: 2.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
