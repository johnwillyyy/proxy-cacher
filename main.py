from socket import *
import sys
import os # Import the OS module to create directories

if len(sys.argv) <= 1:
    print('Usage: "python ProxyServer.py server_ip"\n[server_ip: It is the IP Address Of Proxy Server')
    sys.exit(2)

# Create a server socket, bind it to a port and start listening
tcpSerSock = socket(AF_INET, SOCK_STREAM)
tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

serverPort = 8888 
tcpSerSock.bind((sys.argv[1], serverPort))
tcpSerSock.listen(5)

while 1:
    # Strat receiving data from the client
    print('Ready to serve...')
    tcpCliSock, addr = tcpSerSock.accept()
    print('Received a connection from:', addr)
    
    message = tcpCliSock.recv(4096).decode()

    if not message:
        tcpCliSock.close()
        continue    

    # Extract the filename from the given message
    print(f"Original request: {message.split()[1]}")
    
    # We get the filename, e.g., www.google.com/images/logo.png
    filename = message.split()[1].partition("//")[2]
    print(f"Parsed filename: {filename}")
    
    # === NEW FIX FOR DIRECTORY REQUESTS ===
    # If the request ends in a / or is just the host,
    # it's a directory request. Append 'index.html' to
    # the filename so we save it as a file.
    
    # Check if the path part is empty or just a slash
    path_only = filename.partition('/')[2]

    if filename.endswith('/'):
        filetouse = "./" + filename + "index.html"
    elif not path_only: # Handles 'info.cern.ch' (no slash)
         filetouse = "./" + filename + "/index.html"
    else:
        filetouse = "./" + filename
    # =======================================
    
    print(f"File to use in cache: {filetouse}")
    
    fileExist = "false"
    
    try:
        # Check wether the file exist in the cache
        f = open(filetouse, "rb") # Open the file using the full path
        outputdata = f.read()
        fileExist = "true"
        
        # ProxyServer finds a cache hit and generates a response message
        tcpCliSock.send("HTTP/1.0 200 OK\r\n".encode())
        tcpCliSock.send("Content-Type: text/html\r\n".encode())
        tcpCliSock.send("\r\n".encode())
        tcpCliSock.send(outputdata)
        f.close()
        
        print('Read from cache')
    
    # Error handling for file not found in cache
    except IOError:
        if fileExist == "false":
            # Create a socket on the proxyserver
            c = socket(AF_INET, SOCK_STREAM)     
            try:
                hostn = filename.split('/')[0]
            except Exception:
                print("Error: Invalid hostname in request.")
                tcpCliSock.close()
                continue
                
            print(f"Connecting to host: {hostn}")

            try:
                # Connect to the socket to port 80
                c.connect((hostn, 80))     
                print(f"Connected to {hostn}")
                
                # Re-format the request to be a standard relative request
                # e.g., GET /images/logo.png HTTP/1.0
                # We find the first '/' after the hostname
                path_start = filename.find('/')
                if path_start == -1:
                    path = "/"
                else:
                    path = filename[path_start:]

                request = f"GET {path} HTTP/1.0\r\n"
                request += f"Host: {hostn}\r\n"
                request += "Connection: close\r\n\r\n"
                print(f"Forwarding request to host:\n{request}")
                
                c.send(request.encode())

                response_buffer = b""
                while True:
                    data = c.recv(4096)
                    if not data:
                        break
                    response_buffer += data
                
                # === CACHING FIX ===
                # We must create the directories if they don't exist
                # e.g., create "./www.google.com/images/"
                try:
                    # Get the directory part of the path
                    directory = os.path.dirname(filetouse)
                    if directory:
                        # exist_ok=True means it won't crash if dir exists
                        os.makedirs(directory, exist_ok=True) 
                        
                    tmpFile = open(filetouse,"wb")
                    tmpFile.write(response_buffer)
                    tmpFile.close()
                    print(f"Cached file to {filetouse}")
                except Exception as e:
                    print(f"Error caching file: {e}")
                # ===================
                
                tcpCliSock.send(response_buffer)
                c.close()

            except Exception as e:
                print(f"Connection Error: {e}")
                tcpCliSock.send("HTTP/1.0 404 Not Found\r\n".encode())
                tcpCliSock.send("\r\n".encode())
                if 'c' in locals() and c.fileno() != -1:
                    c.close()
        else:
            pass
            
    tcpCliSock.close()