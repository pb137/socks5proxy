import logging
from protocol import Protocol, ProtocolFactory
from connector import Connector


class EchoProtocolFactory(ProtocolFactory):
    """Creates EchoProtocol protocol instances."""
    def create(self):
        return Echo()


class Echo(Protocol):
    """Echo server. This is an example to show how easy it should be to write a server"""
    def data_received(self, data):
        logging.info(f"data_received: {data}")
        self.write(data)

    def connection_lost(self):
        logging.info("Connection Lost")


def main():
    logging.basicConfig(level=logging.DEBUG)
    connector = Connector()
    connector.create_server('localhost', 1080, EchoProtocolFactory())
    connector.start()


if __name__ == '__main__':
    main()

