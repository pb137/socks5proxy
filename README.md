# SOCKS 5 Proxy

A simple SOCKS5 proxy. Written as an exercise to understand how to write an aysnchronous network server using select rather than a framework such as ayncio or Twisted. Not suitable for production use. Functional, but not extensively tested.

Command line arguments:
```
usage: socks5app.py [-h] [--password_file PASSWORD_FILE] [--loglevel LOGLEVEL] [--port PORT]

Socks5 Proxy.

optional arguments:
  -h, --help            show this help message and exit
  --password_file PASSWORD_FILE
  --loglevel LOGLEVEL   DEBUG, INFO, WARNING or ERROR
  --port PORT
```

The password file is a csv containing base64 encoded user and password strings.
