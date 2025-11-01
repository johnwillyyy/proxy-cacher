from socket import *
import sys
import os
import traceback

# ===============================
# CONFIGURATION
# ===============================
SERVER_PORT = 8888
BUFFER_SIZE = 4096
TIMEOUT = 10 
CACHE_ROOT = "./"

# ===============================
# STARTUP
# ===============================
if len(sys.argv) <= 1:
    print('Usage: "python ProxyServer.py server_ip"\n[server_ip: It is the IP Address Of Proxy Server]')
    sys.exit(2)

tcpSerSock = socket(AF_INET, SOCK_STREAM)
tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

try:
    tcpSerSock.bind((sys.argv[1], SERVER_PORT))
    tcpSerSock.listen(5)
    print(f"Proxy server started on {sys.argv[1]}:{SERVER_PORT}")
except Exception as e:
    print(f"Error starting proxy server: {e}")
    sys.exit(1)

# ===============================
# MAIN LOOP
# ===============================
while True:
    try:
        print('Ready to serve...')
        tcpCliSock, addr = tcpSerSock.accept()
        print('Received a connection from:', addr)

        try:
            message = tcpCliSock.recv(BUFFER_SIZE).decode(errors="ignore")
        except Exception as e:
            print(f"Receive error: {e}")
            tcpCliSock.close()
            continue

        if not message or len(message.split()) < 2:
            print("Invalid or empty HTTP request.")
            tcpCliSock.close()
            continue

        method = message.split()[0].upper()
        url = message.split()[1]
        print(f"{method} request for: {url}")

        filename = url.partition("//")[2]
        path_only = filename.partition('/')[2]
        if filename.endswith('/'):
            filetouse = os.path.join(CACHE_ROOT, filename, "index.html")
        elif not path_only:
            filetouse = os.path.join(CACHE_ROOT, filename, "index.html")
        else:
            filetouse = os.path.join(CACHE_ROOT, filename)

        print(f"Cache file path: {filetouse}")

        # ===============================
        # SERVE FROM CACHE (for GET)
        # ===============================
        if method == "GET":
            try:
                with open(filetouse, "rb") as f:
                    cached_response = f.read()
                print("Cache hit: serving exact cached response.")
                try:
                    tcpCliSock.sendall(cached_response)
                except BrokenPipeError:
                    print("Client disconnected early (Broken pipe).")
                tcpCliSock.close()
                continue
            except FileNotFoundError:
                print("Cache miss: file not found locally.")
            except Exception as e:
                print(f"Error reading cache: {e}")

        # ===============================
        # FETCH FROM REMOTE SERVER
        # ===============================
        try:
            hostn = filename.split('/')[0]
            if not hostn:
                raise ValueError("Invalid or missing hostname in URL.")

            c = socket(AF_INET, SOCK_STREAM)
            c.settimeout(TIMEOUT)
            print(f"Connecting to remote host: {hostn}")
            c.connect((hostn, 80))
            print(f"Connected to {hostn}")

            headers, _, body = message.partition("\r\n\r\n")
            headers_lines = headers.splitlines()
            path_start = filename.find('/')
            path = filename[path_start:] if path_start != -1 else "/"

            # Build proper request
            request_lines = []
            for line in headers_lines:
                if line.startswith("GET") or line.startswith("POST"):
                    request_lines.append(f"{method} {path} HTTP/1.0")
                elif not line.lower().startswith("connection:"):
                    request_lines.append(line)
            request_lines.append("Connection: close")
            request_data = "\r\n".join(request_lines) + "\r\n\r\n"

            if method == "POST":
                request_bytes = request_data.encode() + body.encode()
            else:
                request_bytes = request_data.encode()

            c.sendall(request_bytes)
            print(f"Forwarded {method} request to {hostn}")

            # Receive response (full)
            response_buffer = b""
            while True:
                try:
                    data = c.recv(BUFFER_SIZE)
                    if not data:
                        break
                    response_buffer += data
                except timeout:
                    print(f"Timeout receiving from {hostn}")
                    break
                except Exception as e:
                    print(f"Receive error: {e}")
                    break

            if not response_buffer:
                print("No response from remote host.")
                tcpCliSock.sendall(b"HTTP/1.0 502 Bad Gateway\r\n\r\n")
                c.close()
                tcpCliSock.close()
                continue

            # Cache only full GET responses
            if method == "GET":
                try:
                    directory = os.path.dirname(filetouse)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    with open(filetouse, "wb") as tmpFile:
                        tmpFile.write(response_buffer)
                    print(f"Cached new file: {filetouse}")
                except Exception as e:
                    print(f"Error caching file: {e}")

            try:
                tcpCliSock.sendall(response_buffer)
            except BrokenPipeError:
                print("Client disconnected early (Broken pipe).")
            except Exception as e:
                print(f"Error sending response: {e}")

            c.close()

        except timeout:
            print(f"Timeout connecting to {hostn}")
            tcpCliSock.sendall(b"HTTP/1.0 504 Gateway Timeout\r\n\r\n")
        except gaierror:
            print(f"Unknown host: {filename}")
            tcpCliSock.sendall(b"HTTP/1.0 404 Not Found\r\n\r\n")
        except ConnectionRefusedError:
            print(f"Connection refused by {hostn}")
            tcpCliSock.sendall(b"HTTP/1.0 502 Bad Gateway\r\n\r\n")
        except ValueError as e:
            print(f"Invalid URL: {e}")
            tcpCliSock.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\n")
        except Exception as e:
            print(f"Unexpected fetch error: {e}")
            traceback.print_exc()
            tcpCliSock.sendall(b"HTTP/1.0 500 Internal Server Error\r\n\r\n")
        finally:
            if 'c' in locals():
                try:
                    c.close()
                except:
                    pass

        tcpCliSock.close()

    except KeyboardInterrupt:
        print("\nProxy server shutting down gracefully...")
        tcpSerSock.close()
        sys.exit(0)
    except Exception as e:
        print(f"Top-level error: {e}")
        traceback.print_exc()
        continue
