def test_auditlog_missing_data(client):
    response = client.post('/auditlog')
    # no data, expect 400
    assert response.status_code == 400
    assert 'JSON' in response.get_json()['message']


def test_auditlog_bogus_level(client):
    data = {
        'message': 'something went bump in the night',
        'level': 'curious'}
    response = client.post('/auditlog', json=data)
    assert response.status_code == 400
    assert 'level' in response.get_json()['message']


def test_auditlog_missing_msg(client):
    data = {'user': 10, 'level': 'debug'}
    response = client.post('/auditlog', json=data)
    # no `message`, expect 400
    assert response.status_code == 400
    assert 'message' in response.get_json()['message']


def test_auditlog_post(client):
    data = {
        'user': 'testy@example.com',
        'patient': 'Jones, Bob; 1969-10-10',
        'level': 'warning',
        'message': "No meds!"
    }
    response = client.post('/auditlog', json=data)
    assert response.status_code == 200
