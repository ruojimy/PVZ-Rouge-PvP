"""Read-only relay health check, standard library, no game dependencies."""
import argparse
import json
import socket
import struct


def health(host, port):
    with socket.create_connection((host, port), timeout=5) as sock:
        data = b'{"relay_protocol":1,"action":"health"}'
        sock.sendall(struct.pack('!I', len(data))+data)
        def read(n):
            result = bytearray()
            while len(result) < n:
                chunk = sock.recv(n-len(result))
                if not chunk:raise RuntimeError('relay closed')
                result.extend(chunk)
            return bytes(result)
        size = struct.unpack('!I', read(4))[0]
        if not 0 < size <= 2048:raise RuntimeError('invalid health reply')
        return json.loads(read(size).decode('utf8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('host', nargs='?', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=24562)
    args = parser.parse_args()
    print(json.dumps(health(args.host, args.port), indent=2))
