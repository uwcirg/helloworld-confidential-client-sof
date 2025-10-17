from celery import Celery
from confidential_backend.app import create_app

__celery = None

def create_celery(flask_app=None):
    global __celery
    if __celery is not None:
        return __celery

    flask_app = flask_app or create_app()
    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        backend=flask_app.config["CELERY_RESULT_BACKEND"],
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
celery.autodiscover_tasks(['confidential_backend.cachelaunchrespons'])
