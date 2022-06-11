import logging
from protocol import Protocol

logger = logging.getLogger(__name__)


class RemoteServerProtocol(Protocol):
    """Protocol to connect to remote server as part of a Socks Proxy

    Protocol is configured with a client_protocol to enable data received from
    the remote server to be written to the client.
    """
    def __init__(self, client_protocol):
        Protocol.__init__(self)
        self._client_protocol = client_protocol

    def on_connect(self):
        # Connection to remote server has been created.
        # We need to signal success to the client connection i.e. the socks5 proxy that
        # started the connection
        logger.debug(f"{self._sock.fileno()}:on_connect")
        self._client_protocol.remote_connection_success()

    def data_received(self, data):
        # Data received from the remote connection is written to the client connection
        self._client_protocol.write(data)

    def connection_lost(self):
        logger.debug(f"connection_lost")
        self._client_protocol.closing()
