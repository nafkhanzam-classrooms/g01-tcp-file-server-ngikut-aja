import socket
import threading
import os

HOST = '127.0.0.1'
PORT = 8080
SERVER_DIR = 'server_files'

os.makedirs(SERVER_DIR, exist_ok=True)
clients = []

def send(conn, msg: str):
    conn.sendall((msg + '\n').encode())

def broadcast(msg: str, sender=None):
    for client in clients:
        if client != sender:
            try:
                send(client, f"BCAST|{msg}")
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

def handle_upload(conn, filename, filesize, buffer, addr):
    filepath = os.path.join(SERVER_DIR, filename)
    received = 0

    with open(filepath, 'wb') as f:
        if buffer:
            chunk = buffer[:filesize]
            f.write(chunk)
            received += len(chunk)
            buffer = buffer[len(chunk):]
        while received < filesize:
            chunk = conn.recv(min(4096, filesize - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)

    print(f"[+] {addr} uploaded {filename}")
    send(conn, f"OK|Uploaded {filename}")
    broadcast(f"{addr[1]} uploaded {filename}", conn)
    return buffer

def handle_msg(conn, addr, message):
    broadcast(f"{addr[1]}: {message}", conn)

def handle_client(conn, addr):
    print(f"[+] Connected {addr}")
    clients.append(conn)
    buffer = b""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break

            buffer += data
            while b'\n' in buffer:
                line_bytes, buffer = buffer.split(b'\n', 1)
                line = line_bytes.decode(errors='ignore')
                parts = line.split()
                if not parts:
                    continue
                cmd = parts[0]

                if cmd == '/exit':
                    print(f"[-] {addr} disconnected")
                    return
                elif cmd == '/list':
                    handle_list(conn)
                elif cmd == '/download':
                    if len(parts) < 2:
                        send(conn, "ERROR|Filename required")
                        continue
                    handle_download(conn, parts[1])
                elif cmd == '/upload':
                    if len(parts) < 3:
                        send(conn, "ERROR|Usage: /upload <file> <size>")
                        continue
                    filename = parts[1]
                    filesize = int(parts[2])
                    send(conn, "READY")
                    buffer = handle_upload(conn, filename, filesize, buffer, addr)
                elif cmd == '/msg':
                    message = " ".join(parts[1:])
                    handle_msg(conn, addr, message)
                else:
                    send(conn, "ERROR|Unknown command")
    except Exception as e:
        print(f"[!] Error {addr}: {e}")
    finally:
        if conn in clients:
            clients.remove(conn)
        conn.close()
        print(f"[-] Closed {addr}")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        print("=== Thread Server ===")
        print("Listening... (Multi-client + Broadcast)")

        while True:
            try:
                conn, addr = server.accept()
                t = threading.Thread(target=handle_client, args=(conn, addr))
                t.start()
            except KeyboardInterrupt:
                print("\n[!] Server stopped")
                break

if __name__ == "__main__":
    main()