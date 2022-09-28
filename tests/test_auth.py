from pytest import fixture
from isacc_messaging.auth.helpers import extract_payload, format_as_jwt

@fixture
def encoded_payload():
    # base64 encoded: {"a":"1","b":"41702","e":"SMART-1234"}
    return 'eyJhIjoiMSIsImIiOiI0MTcwMiIsImUiOiJTTUFSVC0xMjM0In0'


@fixture
def example_token():
    return '.'.join((
        'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9',
        'eyJwcm9maWxlIjoiUHJhY3RpdGlvbmVyL1NNQVJULTEyMzQiLCJzdWIiOiI3NmQ1M2Zm'
        'NmNjZDY5ZWEyN2YzMjM5MzgwYjMwMzliNGE4NzI5OTJmODE1MWViMzE4Y2UxODZlZDlm'
        'MmYzMTNjIiwiaXNzIjoiaHR0cHM6Ly9zbWFydC1kZXYtc2FuZGJveC1sYXVuY2hlci5j'
        'aXJnLndhc2hpbmd0b24uZWR1IiwiaWF0IjoxNTg4MDIwNDU3LCJleHAiOjE1ODgwMjQw'
        'NTd9',
        'PyWKOdkS1AUGF6R0s1RWkhLXF2rFKq9m-Xdw4LaJSHKchpDRVpZ_jlpv73D09F3pIRJn'
        'Tq10EJDv34V0UNRiD53IVgdTS680p-kj5t1fpE66aOU-aLQHkaH0mdvGVdXKGHaidda2'
        'Uq-QdoVT17RtKHeVzfKdEOMGbKPUDbKktgVw57JuTrUgtsOihsYKMu5j09J6ZB1K1deg'
        'm2ppl_0DMhP_UJgbniOlgpIyR2QYLTS2Dz-DLsYmPr-anK8d_wVHdXqt3TCnCnYOww8o'
        '6eBsFF_BtbWNO-CYTsnhQB_UKs1TNVrneVoTDGSLZPdcnK1ay23IiA2PTybPrFja6kdz'
        'qQ'))


@fixture
def jwt_sample():
    return "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJfcW5PSE1xeDhidGpldW1CQUVvNjBaQVJoWThxd2Y0WU1ncU1GOEZreHNFIn0.eyJqdGkiOiI4ZGZmMmNiNy1hODUzLTQ4ZWEtOGZjMS01M2ZkMzVjZDEwMGQiLCJleHAiOjE2MzA3MTYwMDksIm5iZiI6MCwiaWF0IjoxNjMwNzE0MjA5LCJpc3MiOiJodHRwczovL2tleWNsb2FrLnBiLmRldi5jb3NyaS5jaXJnLndhc2hpbmd0b24uZWR1L2F1dGgvcmVhbG1zL2ZFTVIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiNzk0ZDI3ODItZTc4My00Y2JiLWFlNzItYjE2NWE0YzA2ZTdmIiwidHlwIjoiQmVhcmVyIiwiYXpwIjoiY29zcmlfb3BlbmlkX2NsaWVudCIsImF1dGhfdGltZSI6MTYzMDcxNDE2Miwic2Vzc2lvbl9zdGF0ZSI6ImI5NzRhZDE1LTg4ZWYtNDFhNi04OGIzLTE1Njk0N2JjZjViOCIsImFjciI6IjAiLCJhbGxvd2VkLW9yaWdpbnMiOlsiKiJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdfSwicmVzb3VyY2VfYWNjZXNzIjp7ImFjY291bnQiOnsicm9sZXMiOlsibWFuYWdlLWFjY291bnQiLCJtYW5hZ2UtYWNjb3VudC1saW5rcyIsInZpZXctcHJvZmlsZSJdfX0sInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJERUEiOiJ0ZXN0REVBdmFsdWUiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInByZWZlcnJlZF91c2VybmFtZSI6InRlc3QifQ.A5LFRH-obxsGov1RMorpY0UFQHiMjL5nbl5oS5fMSPOiE9KG1MdzlIr_5GG4LkBj3G6598rPi6-oPE5A4eM6ZT3wczyglFmW3RbaPfVxAA9zD0wDv77nnPjnFalr54VJdhDIZMn7jRIPSMtFvPq3dO-y6qHaJtwzVlefp1GUwiaZclb4JyMkIc5EMc1fZsvw87PNotNhNlAQpo64Ht8_35RNYOTmtE0W-xUBn-rtXaHE9BSoyZj3pB3AX4sk6PYSE7eIB3ZQnTMCVvYz9o-KQf6WPmSJfyvvFk8EpDoyHSV6yeVDTyHayUf9KfQk6vfogzGLHTOri9ur_1hlI0GYug"


def test_extract(example_token):
    extracted = extract_payload(example_token)
    assert 'profile' in extracted
    assert extracted['profile'] == 'Practitioner/SMART-1234'


def test_enc_payload_extract(encoded_payload):
    jwt = format_as_jwt(encoded_payload)
    assert len(jwt.split('.')) == 3
    assert extract_payload(jwt) == {'a': '1', 'b': '41702', 'e': 'SMART-1234'}


def test_bad_extract():
    jwt = format_as_jwt('ill formed string')
    assert len(jwt.split('.')) == 3
    assert extract_payload(jwt) == {}
