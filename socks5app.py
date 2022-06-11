import logging
import argparse
from authenticator import Authenticator
from connector import Connector
from errors import AuthenticatorError
from socks5_server import Socks5ProtocolFactory

logger = logging.getLogger(__name__)


def configure_connection_logger():
    # Setup logger to record connection events
    conn_formatter = logging.Formatter("%(asctime)s - %(message)s")
    conn_handler = logging.FileHandler("connection.log")
    conn_handler.setFormatter(conn_formatter)
    conn_logger = logging.getLogger("ConnectionLogger")
    # Stop connection events appearing in main log
    conn_logger.propagate = False
    conn_logger.setLevel(logging.INFO)
    conn_logger.addHandler(conn_handler)


def main():

    parser = argparse.ArgumentParser(description="Socks5 Proxy.")
    parser.add_argument("--password_file", default="password_file")
    parser.add_argument("--loglevel", default="WARN", help="DEBUG, INFO, WARNING or ERROR")
    parser.add_argument("--port", type=int, default=1080)
    args = parser.parse_args()

    configure_connection_logger()

    # Configure basic logging
    if args.loglevel == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    elif args.loglevel == "INFO":
        logging.basicConfig(level=logging.INFO)
    elif args.loglevel == "WARN":
        logging.basicConfig(level=logging.WARN)
    elif args.loglevel == "ERROR":
        logging.basicConfig(level=logging.ERROR)

    # Create simple username / password authenticator. Exit if can't find password file
    authenticator = None
    try:
        authenticator = Authenticator(args.password_file)
    except AuthenticatorError as e:
        logger.error(e)
        exit()

    connector = Connector()
    connector.create_server('0.0.0.0', args.port, Socks5ProtocolFactory(authenticator))
    connector.start()


if __name__ == '__main__':
    # Shutdown quietly
    try:
        main()
    except KeyboardInterrupt:
        pass