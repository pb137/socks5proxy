import ipaddress
from errors import ProtocolError
from ipaddress import ip_address


class Socks5:
    """Static methods for handling limited set of Socks5 protocol"""

    PROTOCOL_VERSION = 0x05

    # Authentication constants
    AUTH_OK = 0x00
    AUTH_FAIL = 0xFF
    NO_AUTH = 0x00
    USER_PWD = 0x02
    NO_METHOD = 0xFF

    # Preferred authentication methods
    AUTH_METHODS = [USER_PWD, NO_AUTH]

    # Client greeting constants
    MIN_CLIENT_GREETING_LEN = 3
    PROTOCOL_INDEX = 0
    AUTH_METHODS_INDEX = 1

    # Username password constants
    MIN_CLIENT_AUTH_LEN = 5
    AUTH_VER_INDEX = 0x00
    AUTH_ULEN_INDEX = 0x01
    AUTH_VERSION = 0x01

    # Connection request constants
    MIN_CLIENT_CONN_LEN = 8
    COMMAND_INDEX = 0x01
    COMMAND_STREAM = 0x01
    RESERVED_INDEX = 0x02
    RESERVED_VALUE = 0x00
    ADDRESS_INDEX = 0x03
    ADDRESS_IPV4 = 0x01
    ADDRESS_DOMAIN = 0x03
    ADDRESS_IPV6 = 0x04
    REQUEST_GRANTED = 0x00
    CONNECTION_REFUSED = 0x05

    @staticmethod
    def handle_client_greeting(data):
        auth_methods = Socks5.parse_client_greeting(data)
        auth_method = Socks5.choose_auth_method(auth_methods)
        return auth_method, Socks5.greeting_response(auth_method)

    @staticmethod
    def choose_auth_method(auth_methods):
        for auth_method in Socks5.AUTH_METHODS:
            if auth_method in auth_methods:
                return auth_method
        return Socks5.NO_METHOD

    @staticmethod
    def parse_client_greeting(data):
        """Returns a list of authentication method bytes"""
        if len(data) < Socks5.MIN_CLIENT_GREETING_LEN:
            raise ProtocolError(f"Client greeting too small {len(data)} < {Socks5.MIN_CLIENT_GREETING_LEN}")
        if data[Socks5.PROTOCOL_INDEX] != Socks5.PROTOCOL_VERSION:
            raise ProtocolError(f"Invalid socks version")
        if data[Socks5.AUTH_METHODS_INDEX] == 0:
            raise ProtocolError(f"Too few auth methods")
        n_auth = data[Socks5.AUTH_METHODS_INDEX]
        min_length = n_auth + Socks5.MIN_CLIENT_GREETING_LEN - 1
        if len(data) < min_length:
            raise ProtocolError(f"Client greeting too small {len(data)} < {min_length}")

        return [x for x in data[(Socks5.AUTH_METHODS_INDEX+1):(Socks5.AUTH_METHODS_INDEX+1+n_auth)]]

    @staticmethod
    def parse_username_password(data):
        if len(data) < Socks5.MIN_CLIENT_AUTH_LEN:
            raise ProtocolError(f"Client authentication too small {len(data)} < {Socks5.MIN_CLIENT_AUTH_LEN}")
        if data[Socks5.AUTH_VER_INDEX] != Socks5.AUTH_VERSION:
            raise ProtocolError(f"Invalid username password authentication version")
        ulen = data[Socks5.AUTH_ULEN_INDEX]
        if len(data) < Socks5.AUTH_ULEN_INDEX+1+ulen:
            raise ProtocolError(f"Username too small")
        username = data[(Socks5.AUTH_ULEN_INDEX+1):(Socks5.AUTH_ULEN_INDEX+1+ulen)]
        plen_index = Socks5.AUTH_ULEN_INDEX+1+ulen
        if len(data) < plen_index:
            raise ProtocolError(f"Password too small")
        plen = data[plen_index]
        if len(data) < plen_index+1+plen:
            raise ProtocolError(f"Password too small")
        password = data[(plen_index+1):(plen_index+1+plen)]
        return username, password

    @staticmethod
    def parse_connection_request(data):
        if len(data) < Socks5.MIN_CLIENT_CONN_LEN:
            raise ProtocolError(f"Connection request too small {len(data)} < {Socks5.MIN_CLIENT_AUTH_LEN}")
        if data[Socks5.PROTOCOL_INDEX] != Socks5.PROTOCOL_VERSION:
            raise ProtocolError(f"Invalid socks version")
        if data[Socks5.COMMAND_INDEX] != Socks5.COMMAND_STREAM:
            raise ProtocolError(f"Invalid command. This proxy only supports stream connections")
        if data[Socks5.RESERVED_INDEX] != Socks5.RESERVED_VALUE:
            raise ProtocolError(f"Invalid reserved value")

        #TODO - remove magic numbers from this section
        addr_type = data[Socks5.ADDRESS_INDEX]
        if addr_type == Socks5.ADDRESS_IPV4:
            addr = str(ip_address(int.from_bytes(data[4:8], byteorder="big", signed=False)))
            port = int.from_bytes(data[8:10], byteorder="big", signed=False)
            return addr, port, Socks5.ADDRESS_IPV4
        elif addr_type == Socks5.ADDRESS_DOMAIN:
            alen = data[4]
            addr = data[5:5+alen].decode('ascii')
            port = int.from_bytes(data[5+alen:7+alen], byteorder="big", signed=False)
            return addr, port, Socks5.ADDRESS_DOMAIN
        elif addr_type == Socks5.ADDRESS_IPV6:
            addr = str(ip_address(int.from_bytes(data[4:20], byteorder="big", signed=False)))
            port = int.from_bytes(data[20:22], byteorder="big", signed=False)
            return addr, port, Socks5.ADDRESS_IPV6
        else:
            raise ProtocolError(f"Invalid address type")

    @staticmethod
    def greeting_response(auth_method):
        return bytearray([Socks5.PROTOCOL_VERSION, auth_method])

    @staticmethod
    def authentication_success():
        return bytearray([Socks5.AUTH_VERSION, Socks5.AUTH_OK])

    @staticmethod
    def authentication_failure():
        return bytearray([Socks5.AUTH_VERSION, Socks5.AUTH_FAIL])

    @staticmethod
    def connection_success(host, port):
        return Socks5._connection_response(host, port, Socks5.REQUEST_GRANTED)

    @staticmethod
    def connection_failure(host, port):
        return Socks5._connection_response(host, port, Socks5.CONNECTION_REFUSED)

    @staticmethod
    def _connection_response(host, port, status):
        addr = ipaddress.ip_address(host)
        if isinstance(addr, ipaddress.IPv4Address):
            response = bytearray([Socks5.PROTOCOL_VERSION, status, Socks5.RESERVED_VALUE, Socks5.ADDRESS_IPV4])
            response.extend(addr.packed)
            response.extend(port.to_bytes(2, "big"))
            return response
        elif isinstance(addr, ipaddress.IPv6Address):
            response = bytearray([Socks5.PROTOCOL_VERSION, status, Socks5.RESERVED_VALUE, Socks5.ADDRESS_IPV6])
            response.extend(addr.packed)
            response.extend(port.to_bytes(2, "big"))
            return response
