import functools
import logging
from errors import ProtocolError
from protocol import Protocol, ProtocolFactory
from remote_server_protocol import RemoteServerProtocol
from socks5 import Socks5

logger = logging.getLogger(__name__)


class Socks5ProtocolFactory(ProtocolFactory):

    def __init__(self, authenticator):
        self._authenticator = authenticator

    def create(self):
        return Socks5Protocol(self._authenticator)


class Socks5Protocol(Protocol):

    conn_logger = logging.getLogger("ConnectionLogger")

    def __init__(self, authenticator):
        Protocol.__init__(self)
        # Username / password authenticator
        self._authenticator = authenticator

        # Function that handles incoming data. This changes as protocol progresses
        self._data_received_handler = self._client_greeting

        # Connection to remote host
        self._remote_server_protocol = None

    def data_received(self, data):
        # Incoming data is just passed to the current handler
        self._data_received_handler(data)

    def connection_lost(self):
        logger.debug(f"connection_lost")
        if self._remote_server_protocol is not None:
            self._remote_server_protocol.closing()

    def _client_greeting(self, data):
        logger.debug(f"{self._sock.fileno()}:client_greeting")
        try:
            auth_method, response = Socks5.handle_client_greeting(data)
            self.write(response)
            if auth_method == Socks5.NO_METHOD:
                # Close socket after writing buffered data
                logger.debug(f"{self._sock.fileno()}:client_greeting:no supported method")
                self.closing()
            elif auth_method == Socks5.NO_AUTH:
                logger.debug(f"{self._sock.fileno()}:client_greeting:no auth")
                self._data_received_handler = self._parse_client_connection_request
            elif auth_method == Socks5.USER_PWD:
                logger.debug(f"{self._sock.fileno()}:client_greeting:username password")
                self._data_received_handler = self._username_password_authentication
        except ProtocolError as e:
            logger.warning(f"{self._sock.fileno()}:Error parsing client greeting: {e}")
            self.close()

    def _username_password_authentication(self, data):
        try:
            username, password = Socks5.parse_username_password(data)
            logger.debug(f"{self._sock.fileno()}:username_password_authentication:username:{username}:password:{password}")
            if self._authenticator.authenticate(username=username, password=password):
                logger.debug(f"{self._sock.fileno()}:username_password_authentication:success")
                self.write(Socks5.authentication_success())
                self._data_received_handler = self._parse_client_connection_request
            else:
                logger.debug(f"{self._sock.fileno()}:username_password_authentication:failure")
                self.write(Socks5.authentication_failure())
                self.closing()
        except ProtocolError as e:
            logger.warning(f"{self._sock.fileno()}:Error parsing authentication: {e}")
            self.close()

    def _parse_client_connection_request(self, data):
        try:
            remote_addr, remote_port, addr_type = Socks5.parse_connection_request(data)
            # Call gethostbyname on connector, passing in callback once complete, to stop blocking other connections
            if addr_type == Socks5.ADDRESS_DOMAIN:
                self._connector.gethostbyname(
                    remote_addr,
                    functools.partial(self._make_client_connection_request, remote_port=remote_port, hostname=remote_addr)
                )
            else:
                self._make_client_connection_request(remote_addr=remote_addr, remote_port=remote_port)
        except ProtocolError as e:
            logger.warning(f"{self._sock.fileno()}:Error parsing connection request: {e}")
            self.close()

    def _make_client_connection_request(self, remote_addr, remote_port, hostname="UNKNOWN"):
        try:
            client_addr, client_port = self.peer_connection_parameters()
            logger.debug(f"{self._sock.fileno()}:make_client_connection_request:hostname:{hostname}:addr:{remote_addr}:port:{remote_port}")
            Socks5Protocol.conn_logger.info(f"Request:from:{client_addr}:{client_port}:to:hostname:{hostname}:{remote_addr}:{remote_port}")
            self._remote_server_protocol = RemoteServerProtocol(self)
            self._connector.create_client(
                remote_addr, remote_port,
                self._remote_server_protocol,
                self.remote_connection_failure
            )
            self._data_received_handler = self._null_data_received_handler
        except OSError as e:
            logger.warning(f"{self._sock.fileno()}:make_client_connection_request:error:{e}")

    def remote_connection_failure(self):
        # Get here via a failure of remote connection.
        # Need to return failure condition and close
        logger.debug(f"{self._sock.fileno()}:remote_connection_failure")
        addr, port = self.local_connection_parameters()
        self.write(Socks5.connection_failure(addr, port))
        self.closing()

    def remote_connection_success(self):
        # Remote connection has started - we can now proxy data
        logger.debug(f"{self._sock.fileno()}:remote_connection_success")
        addr, port = self.local_connection_parameters()
        self.write(Socks5.connection_success(addr, port))
        self._data_received_handler = self._proxy_data

    def _null_data_received_handler(self, data):
        # This should never be called as we should only be in this state when
        # we are waiting for the remote connection to be created.
        # The socks client should not send any data on this connection in this period.
        # We may need to buffer the data without writing it if the socks client is aggressive though
        logger.debug(f"{self._sock.fileno()}:null_data_received_handler")
        self.close()

    def _proxy_data(self, data):
        self._remote_server_protocol.write(data)

