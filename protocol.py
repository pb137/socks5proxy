import functools
import logging
import selectors
from errors import ProtocolError

logger = logging.getLogger(__name__)


class ProtocolFactory:
    """Factory for Protocol objects. This class must be implemented to enable a server
    to create new Protocol instances
    """
    def create(self):
        """Return a Protocol instance"""
        pass


class Protocol:
    """Handler for event driven networking. Manages reading and writing to the network.

    Override on_connect, data_received and connection_lost to implement business logic
    """

    BUFSIZE = 8192

    def __init__(self):
        self._connector = None
        self._selector = None
        self._sock = None
        self._local_addr = ""
        self._local_port = 0
        self._peer_addr = ""
        self._peer_port = 0
        self._write_buffer = bytearray()
        self._write_handler = None  # Called when application wants to write data to the network
        self._writer = None         # Called to write to network
        self._reader = None         # Called to read from network
        self._closer = None         # Called to close network connection
        self._set_unconnected()

    def on_connect(self):
        """Called when a new connection is connected.
        Override this method to provide protocol specific initialization code
        """
        pass

    def data_received(self, data):
        """Called when data is received from the network.
        Override this to implement your protocol
        """
        pass

    def connection_lost(self):
        """Called when network connection has been closed."""
        pass

    def write(self, data):
        """Buffers data for writing to network. You should not need to override this method.
        If you do, make sure you actually call it to write data to the network
        """
        self._write_handler(data)

    def closing(self):
        """Signal connections should close after writing buffered data.
        If there is no data to write, the connection will be closed immediately"""

        logger.debug(f"{self.sockid()}:closing")
        if len(self._write_buffer) == 0:
            # This will close socket and set handlers to closed state
            self._closer(self._sock)
        else:
            # Set handlers to closing state
            self._set_closing()

    def close(self):
        """Closes connection immediately without writing buffered data"""
        logger.debug(f"{self.sockid()}:close")
        self.closer(self._sock)

    def sockid(self):
        """Return socket identifier string """
        if self._sock is None:
            return "None"
        return self._sock.fileno()

    def local_connection_params(self):
        return self._local_addr, self._local_port

    def peer_connection_params(self):
        return self._peer_addr, self._peer_port

    def _set_unconnected(self):
        """Called when a socket is started or closed. Prevents any attempts to read or write data
        or to double close a socket"""
        self._write_handler = self._null_write_handler
        self._writer = self._null_network_handler
        self._reader = self._null_network_handler
        self._closer = self._null_closer

    def _set_connected(self):
        """Called when socket is connected. Sets the read, write and close handlers to enable socket to be used"""
        self._write_handler = self._connected_write_handler
        self._writer = self._connected_writer
        self._reader = self._connected_reader
        self._closer = self._connected_closer

    def _set_closing(self):
        """Called when closing a socket.
        Sets the reader to a null function that prevents reading.
        Sets the writer to writer that will close once buffered data is written"""
        self._write_handler = self._null_write_handler
        self._writer = self._closing_writer
        self._reader = self._null_network_handler
        self._closer = self._connected_closer

    def _connection_created(self, connector, selector, sock, on_failure=None):
        """Called when a new connection is created.
        This is called in preference to a constructor to avoid subclasses needing to push
        arguments through to a superclass constructor.
        """
        self._connector = connector
        self._selector = selector
        self._sock = sock

        logger.debug(f"{self.sockid()}:connection_created")

        # Wait for socket to become writable, at which point we can check for success
        try:
            self._selector.register(
                self._sock,
                selectors.EVENT_WRITE,
                functools.partial(self._connection_complete, on_failure=on_failure)
            )
        except (ValueError, KeyError)  as e:
            logger.debug(f"Selector registration error: {e}")
            if on_failure is not None:
                on_failure()

    def _connection_complete(self, sock, make, on_failure):
        """Called once socket is writeable after it has been created.
        The socket could have connected, but it may have failed.
        A call to getpeername will detect if connection has failed.
        """
        logger.debug(f"{self.sockid()}:connection_complete")

        # Check our socket has been created and that we are connected by checking peername
        if self._sock is not None:
            try:
                (self._peer_addr, self._peer_port) = self._sock.getpeername()
                (self._local_addr, self._local_port) = self._sock.getsockname()
            except OSError as e:
                logger.debug(f"Connection failed on name lookup: {e}")
                if on_failure is not None:
                    logger.debug(f"{self.sockid()}:calling on_failure")
                    on_failure()
            else:
                # Set handlers to deal with running connection
                self._set_connected()

                # Connected - call protocol custom setup code
                self.on_connect()

                # Register socket for reading
                try:
                    self._selector.modify(self._sock, selectors.EVENT_READ, self._read)
                except (ValueError, KeyError)  as e:
                    logger.debug(f"Selector registration error: {e}")
                    if on_failure is not None:
                        on_failure()
        else:
            logger.debug("Socket is none")
            if on_failure is not None:
                on_failure()

    def _connected_write_handler(self, data):
        """Called by application in connected state. Buffer data and wait for network"""
        self._write_buffer.extend(data)
        try:
            self._selector.modify(self._sock, selectors.EVENT_WRITE, self._write)
        except (ValueError, KeyError) as e:
            logger.debug(f"Selector registration error: {e}")
            self._close(self._sock)

    def _null_write_handler(self, data):
        """Null function to handle write after a call to closing or when socket is closed. Do nothing"""
        pass

    def _read(self, sock, mask):
        """Called when socket is ready to be read"""
        self._reader(sock, mask)

    def _connected_reader(self, sock, mask):
        """Called when socket is connected. Reads data from the network and calls data_received."""
        try:
            data = sock.recv(self.BUFSIZE)
            if len(data) == 0:
                self._close(sock)
            else:
                self.data_received(data)
        except OSError as e:
            # Catch a 'Errno 104: connection reset by peer' if remote server resets
            logger.debug(f"{sock.fileno()}:_read:error{e}")
            self._close(sock)

    def _write(self, sock, mask):
        """Called when socket is writable"""
        self._writer(sock, mask)

    def _connected_writer(self, sock, mask):
        """Writes data to the network when in a connected state"""
        try:
            n_bytes = sock.send(self._write_buffer)
            self._write_buffer = self._write_buffer[n_bytes:]
            if len(self._write_buffer) == 0:
                self._selector.modify(sock, selectors.EVENT_READ, self._read)
        except OSError as e:
            logger.debug(f"{sock.fileno()}:_write:error{e}")
            self._close(sock)

    def _closing_writer(self, sock, mask):
        """Writes data to the network. Called once closing has been called.
        Closes socket when all buffered data is written"""
        try:
            n_bytes = sock.send(self._write_buffer)
            self._write_buffer = self._write_buffer[n_bytes:]
            if len(self._write_buffer) == 0:
                self._close(sock)
        except OSError as e:
            logger.debug(f"{sock.fileno()}:_write:error{e}")
            self._close(sock)

    def _null_network_handler(self, sock, mask):
        """Called by reader and writer when socket is closing or closed. Do nothing"""
        pass

    def _close(self, sock):
        self._closer(sock)

    def _connected_closer(self, sock):
        """Called when in connected or closing state.
        Close network connection and call connection_lost."""
        logger.debug(f"{sock.fileno()}:_close")
        try:
            self._selector.unregister(sock)
        except ValueError as e:
            logging.debug("Invalid socket id - already closed")
        except KeyError as e:
            logging.debug("Socket not registered")
        sock.close()
        self._set_unconnected()
        self.connection_lost()

    def _null_closer(self, sock):
        """Called when socket has already been closed. Prevents multiple close errors"""
        pass

