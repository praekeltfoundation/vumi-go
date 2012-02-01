# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

import os

from celery.app import app_or_default


def setup_celery_for_tests():
    """Setup celery for tests."""
    celery_config = os.environ.get("CELERY_CONFIG_MODULE")
    os.environ["CELERY_CONFIG_MODULE"] = "celery.tests.config"
    app = app_or_default()
    always_eager = app.conf.CELERY_ALWAYS_EAGER
    app.conf.CELERY_ALWAYS_EAGER = True
    return app, celery_config, always_eager


def restore_celery(app, celery_config, always_eager):
    if celery_config is None:
        del os.environ["CELERY_CONFIG_MODULE"]
    else:
        os.environ["CELERY_CONFIG_MODULE"] = celery_config
    app.conf.CELERY_ALWAYS_EAGER = always_eager
