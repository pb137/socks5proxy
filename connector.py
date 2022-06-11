import atexit
import logging
import selectors
import socket
import functools
import threading

logger = logging.getLogger(__name__)


class Connector:
    """Manages network using an event driven approach"""

    EINPROGRESS = 115

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        atexit.register(self.shutdown)

    def create_client(self, addr, port, protocol, on_failure=None):
        """Create a network client

        Arguments:
        addr -- the remote server address
        port -- the remote server port
        protocol -- the Protocol instance used to manage the connection
        """
        sock = socket.socket()
        sock.setblocking(False)
        try:
            sock.connect((addr, port))
        except OSError as e:
            # We expect a non-blocking socket to initially fail.
            # Later fails will be caught in selector loop when socket reads and writes fail
            if e.errno != Connector.EINPROGRESS:
                logger.warning(f"Unexpected error creating socket: {e}")

        # Configure protocol with connector, selector and socket
        protocol._connection_created(self, self.selector, sock, on_failure)

    def create_server(self, interface, port, protocol_factory):
        """Create a server for processing network events.

        Arguments:
        interface -- the listener interface (e.g. 0.0.0.0)
        port -- the listening port
        protocol_factory -- an instance of a ProtocolFactory class used to manage new server connections
        """
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((interface, port))
        sock.listen(100)
        sock.setblocking(False)

        # Socket is registered to handle new connections using the accept method
        self.selector.register(sock, selectors.EVENT_READ, functools.partial(self.accept, protocol_factory=protocol_factory))

    def accept(self, sock, mask, protocol_factory):
        """Accept a new server connection."""
        # Create new non-blocking connection
        conn, addr = sock.accept()
        conn.setblocking(False)

        # Create new protocol object to handle connection
        protocol = protocol_factory.create()

        # Configure protocol with connector, se)result_handlerlector and socket
        protocol._connection_created(self, self.selector, conn)

    def gethostbyname(self, hostname, callback):
        """Non-blocking version of gethostbyname()

        Arguments:
            hostname - hostname to look up
            callback - function to call with result. Result will passed in as a parameter
        """
        thread = threading.Thread(target=functools.partial(Connector._gethostbyname_lookup, hostname=hostname, callback=callback))
        thread.start()
        return

    @staticmethod
    def _gethostbyname_lookup(hostname, callback):
        """Lookup address of hostname. This is called in a separate thread.
        The result is returned in a callback
        """
        # This will be called in a thread
        addr = socket.gethostbyname(hostname)
        callback(addr)

    def start(self):
        """Starts processing network events"""
        while True:
            events = self.selector.select()
            for key, mask in events:
                # Function called on a network event is stored in data field of key
                callback = key.data
                callback(key.fileobj, mask)

    def shutdown(self):
        logger.debug("Shutting down")
        self.selector.close()

