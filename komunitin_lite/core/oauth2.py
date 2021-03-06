import time
import requests
import logging

from komunitin_lite.core.local_storage import (
    get_local_data, put_local_data, KomunitinFileError)


logger = logging.getLogger('KomLite')


class KomunitinNetError(Exception):
    def __init__(self, message, status_code=0):
        super().__init__(message)
        self.status_code = status_code


class KomunitinAuthError(Exception):
    pass


class ApiAccess:

    def __init__(self, config):
        self.server = config["server"]
        self.has_access = False
        self.headers = {}
        self.user = ""
        self._auth = {}

    def get_local_auth(self):
        self._auth = self._read_initial_auth()
        if self._auth:
            # valid token, so try to refresh it.
            try:
                self._refresh_auth_token()
            except Exception:
                self._auth = {}

    def new_access(self, user, password):
        # Try to authenticate and get token.
        error = ""
        try:
            self._get_auth_token(user, password)
        except KomunitinAuthError as e:
            self.has_access = False
            error = "Wrong credentials: {}".format(e)
        except (KomunitinNetError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as e:
            self.access = False
            error = 'Network Error: {}'.format(e)
        except KomunitinFileError:
            self.access = True

        return self.has_access, error

    def _read_initial_auth(self):
        try:
            kdata = get_local_data()
        except KomunitinFileError:
            return {}
        self.user = kdata["user"] if "user" in kdata else ""
        if "auth" in kdata:
            # check if token is expired
            expire = (int(kdata["auth"]["created"]) +
                      int(kdata["auth"]["expires_in"]))
            if int(time.time()) > expire:
                # expired token.
                return {}

        return kdata["auth"] if "auth" in kdata else {}

    def _get_auth_token(self, user, password):
        params = {
            "grant_type": "password",
            "username": user,
            "password": password,
            "client_id": self.server["oauth2_client_id"],
            # "client_secret": self.server["oauth2_client_password"],
            "scope": self.server["oauth2_scope"]
        }
        response = requests.post(self.server["oauth2_token_url"], params,
                                 timeout=5)
        if response.status_code == 200:
            self.user = user
            self._auth = response.json()
            self._auth["created"] = int(time.time())
            self.has_access = True
            self.headers = self._make_headers(self._auth['access_token'])
            put_local_data({"user": self.user, "auth": self._auth})
            logging.debug("Authentication done")
        elif response.status_code == 401:
            # Authentication fail
            self.has_access = False
            logger.info("Authentication fail: {} {}"
                        .format(response.status_code, response.text))
            raise KomunitinAuthError(response.text)
        else:
            logger.error("Error sending auth: {} {}"
                         .format(response.status_code, response.text))
            raise KomunitinNetError(response.text, response.status_code)

    def _refresh_auth_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self._auth["refresh_token"],
            "username": self.user,
            "client_id": self.server["oauth2_client_id"],
            "scope": self.server["oauth2_scope"]
        }
        response = requests.post(self.server["oauth2_token_url"], params,
                                 timeout=5)
        if response.status_code == 200:
            self.has_access = True
            self._auth = response.json()
            self._auth["created"] = int(time.time())
            self.headers = self._make_headers(self._auth['access_token'])
            put_local_data({"user": self.user, "auth": self._auth})
            logger.debug("Token refreshed")
        else:
            logger.warning("Cannot refresh a non-expired token: {} {}".
                           format(response.status_code, response.text))
            raise KomunitinNetError(response.text, response.status_code)

    def _make_headers(self, token):
        return {
            'Content-Type': 'application/vnd.api+json',
            'Authorization': 'Bearer ' + token
        }
