import csv
from base64 import b64decode
from errors import AuthenticatorError


class Authenticator:

    def __init__(self, password_filename):
        self._passwords = {}
        self._initialize(password_filename)

    def _initialize(self, password_filename):
        """Usernames and passwords are stored base64 encoded in a csv file: user,password.
        Usernames and passwords are compared in binary
        """
        self._passwords = {}
        try:
            with open(password_filename, "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) == 2:
                        username = b64decode(row[0])
                        password = b64decode(row[1])
                        self._passwords[username] = password
        except FileNotFoundError as e:
            raise AuthenticatorError(f"Authenticator: initialization error: {e}")

    def authenticate(self, username, password):
        if username in self._passwords and self._passwords[username] == password:
            return True
        else:
            return False
