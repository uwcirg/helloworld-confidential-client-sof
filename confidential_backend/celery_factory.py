from flask import current_app
from confidential_backend.app import create_app

__celery = None

def get_celery_class():
    try:
        from celery import Celery
        return Celery
    except ImportError:
        raise ValueError("Application configured to use celery, but not installed")


def celery_task(func):
    """Decorator to register a celery task if enabled, or run synchronously"""
    def wrapper(*args, **kwargs):
        celery = current_app.extensions.get('celery')
        if celery:
            task = celery.task(func)
            return task.delay(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper


def create_celery(flask_app=None):
    global __celery
    if __celery is not None:
        return __celery

    flask_app = flask_app or create_app()
    if not flask_app.config.get("USE_CELERY", False):
        return None

    Celery = get_celery_class()
    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        results_backend=flask_app.config["CELERY_BROKER_URL"],
        imports = ('confidential_backend.cachelaunchresponse',)
    )
    celery.conf.update(flask_app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    __celery = celery
    return celery


celery = create_celery()
