import configparser

import requests
from requests import Session, Response
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup


def login(username: str, password: str) -> Session:
    session = requests.Session()
    session.get(url='https://elearning.unitelma.it/')
    redirect_url = \
        session.get(url='https://elearning.unitelma.it/auth/shibboleth/index.php?', allow_redirects=False).headers[
            'Location']
    session.get(url=redirect_url)
    session.post(url='https://idp.unitelma.it/idp/profile/SAML2/Redirect/SSO?execution=e1s1',
                 data=_get_shibboleth_payload())
    response = session.post(url='https://idp.unitelma.it/idp/profile/SAML2/Redirect/SSO?execution=e1s2',
                            data=_get_login_data(username, password), allow_redirects=False)
    session.post(url='https://elearning.unitelma.it/Shibboleth.sso/SAML2/POST',
                 data=_get_SAML_post_data(redirect_url, response))
    return session


def _get_login_data(username: str, password: str) -> dict:
    return {
        'j_username': username,
        'j_password': password,
        '_eventId_proceed': ''
    }


def _get_shibboleth_payload() -> dict:
    return {
        "shib_idp_ls_exception.shib_idp_session_ss": '',
        "shib_idp_ls_success.shib_idp_session_ss": True,
        "shib_idp_ls_value.shib_idp_session_ss": '',
        "shib_idp_ls_exception.shib_idp_persistent_ss": '',
        "shib_idp_ls_success.shib_idp_persistent_ss": True,
        "shib_idp_ls_value.shib_idp_persistent_ss": '',
        "shib_idp_ls_supported": True,
        "_eventId_proceed": ''
    }


def _get_SAML_post_data(url: str, response: Response) -> dict:
    soup = BeautifulSoup(response.content, 'html.parser')
    saml_response_input = soup.find('input', {'name': 'SAMLResponse'})
    saml_response_value = saml_response_input['value']

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return {
        'RelayState': query_params.get('RelayState', [None])[0],
        'SAMLResponse': saml_response_value
    }
