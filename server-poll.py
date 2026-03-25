import socket
import select
import os

HOST = '127.0.0.1'
PORT = 8080
SERVER_DIR = 'server_files'

os.makedirs(SERVER_DIR, exist_ok=True)

def send(conn, msg: str):
    conn.sendall((msg + '\n').encode())

def broadcast(msg: str, sender, clients):
    for sock in clients:
        if sock != sender:
            try:
                send(sock, f"BCAST|{msg}")
            except:
                pass

def handle_list(conn):
    files = os.listdir(SERVER_DIR)
    send(conn, f"LIST_OUT|{','.join(files)}")

def handle_download(conn, filename):
    filepath = os.path.join(SERVER_DIR, filename)
    if not os.path.exists(filepath):
        send(conn, "ERROR|File not found")
        return
    filesize = os.path.getsize(filepath)
    send(conn, f"FILE|{filename}|{filesize}")
    with open(filepath, 'rb') as f:
        conn.sendall(f.read())

def disconnect(fd, poller, fd_map, clients, buffers):
    conn = fd_map.get(fd)
    if conn:
        addr = clients.get(conn, "Unknown")
        print(f"[-] Disconnected {addr}")
        poller.unregister(fd)
        del fd_map[fd]
        if conn in clients:
            del clients[conn]
        if conn in buffers:
            del buffers[conn]
        conn.close()

def main():
    if not hasattr(select, 'poll'):
        print("[!] poll() not supported (use Linux/WSL)")
        return
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    server.setblocking(False)
    poller = select.poll()
    poller.register(server, select.POLLIN)

    fd_map = {server.fileno(): server}
    clients = {}
    buffers = {}
    upload_state = {}
    print("=== Poll Server ===")
    print("Listening... (event-driven)")
    try:
        while True:
            events = poller.poll(1000)
            for fd, flag in events:
                sock = fd_map[fd]
                if sock == server:
                    conn, addr = server.accept()
                    conn.setblocking(False)
                    fd_map[conn.fileno()] = conn
                    poller.register(conn, select.POLLIN)
                    clients[conn] = addr
                    buffers[conn] = b""
                    print(f"[+] Connected {addr}")
                elif flag & (select.POLLIN | select.POLLPRI):
                    try:
                        if sock in upload_state:
                            state = upload_state[sock]
                            try:
                                chunk = sock.recv(min(4096, state["remaining"]))
                            except BlockingIOError:
                                continue
                            if not chunk:
                                disconnect(fd, poller, fd_map, clients, buffers)
                                continue
                            state["file"].write(chunk)
                            state["remaining"] -= len(chunk)
                            if state["remaining"] == 0:
                                state["file"].close()
                                filename = state["filename"]
                                print(f"[+] Uploaded {filename}")
                                send(sock, f"OK|Uploaded {filename}")
                                addr = clients[sock]
                                broadcast(f"{addr[1]} uploaded {filename}", sock, clients)
                                del upload_state[sock]
                            continue
                        data = sock.recv(4096)
                        if not data:
                            disconnect(fd, poller, fd_map, clients, buffers)
                            continue
                        buffers[sock] += data
                        buffer = buffers[sock]
                        while b'\n' in buffer:
                            line_bytes, buffer = buffer.split(b'\n', 1)
                            buffers[sock] = buffer
                            line = line_bytes.decode(errors='ignore')
                            parts = line.split()
                            if not parts:
                                continue
                            cmd = parts[0]
                            addr = clients[sock]

                            # CMD
                            if cmd == '/exit':
                                disconnect(fd, poller, fd_map, clients, buffers)
                                break
                            elif cmd == '/list':
                                handle_list(sock)
                            elif cmd == '/download':
                                if len(parts) < 2:
                                    send(sock, "ERROR|Filename required")
                                    continue
                                handle_download(sock, parts[1])
                            elif cmd == '/upload':
                                if len(parts) < 3:
                                    send(sock, "ERROR|Usage: /upload <file> <size>")
                                    continue

                                filename = parts[1]
                                filesize = int(parts[2])
                                filepath = os.path.join(SERVER_DIR, filename)
                                upload_state[sock] = {
                                    "file": open(filepath, 'wb'),
                                    "remaining": filesize,
                                    "filename": filename
                                }
                                send(sock, "READY")
                            elif cmd == '/msg':
                                message = " ".join(parts[1:])
                                broadcast(f"{addr[1]}: {message}", sock, clients)
                            else:
                                send(sock, "ERROR|Unknown command")

                    except Exception as e:
                        print(f"[!] Error: {e}")
                        disconnect(fd, poller, fd_map, clients, buffers)
                elif flag & (select.POLLHUP | select.POLLERR):
                    disconnect(fd, poller, fd_map, clients, buffers)
    except KeyboardInterrupt:
        print("\n[!] Server stopped")
        for sock in fd_map.values():
            sock.close()

if __name__ == "__main__":
    main()