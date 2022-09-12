from jose import jwt
from jose.exceptions import JWTError


def format_as_jwt(encoded_payload):
    """To extract payload from ill formed JWT, package as per protocol"""
    # base64 encoded string: `{"typ":"JWT","alg":"RS256"}`
    header = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9'
    sig = 'n/a'
    return '.'.join((header, encoded_payload, sig))


def extract_payload(token):
    """Given JWT, extract the payload and return as dict

    Garbage safe to keep client code clean.  If given token can't be
    extracted, catch exception and return {}

    """
    payload = {}
    try:
        payload = jwt.get_unverified_claims(token)
    except JWTError:
        # No value seen in recording at this time
        pass
    return payload
