from pytest import fixture


@fixture
def app():
    from isacc_messaging.app import create_app
    return create_app(testing=True)


@fixture
def client(app):
    with app.test_client() as c:
        yield c
