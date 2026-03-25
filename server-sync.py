import socket
import os

HOST = '127.0.0.1'
PORT = 8080
SERVER_DIR = 'server_files'

os.makedirs(SERVER_DIR, exist_ok=True)

def send(conn, msg: str):
    conn.sendall((msg + '\n').encode())

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

def handle_upload(conn, filename, filesize, buffer):
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
    print(f"[+] File received: {filename}")
    send(conn, f"OK|Uploaded {filename}")
    return buffer

def handle_client(conn, addr):
    print(f"[+] Connected {addr}")
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

                # CMD HANDLER 
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
                    buffer = handle_upload(conn, filename, filesize, buffer)
                elif cmd == '/msg':
                    message = " ".join(parts[1:])
                    send(conn, f"BCAST|You: {message}")
                else:
                    send(conn, "ERROR|Unknown command")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        conn.close()
        print(f"[-] Closed {addr}")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        print("=== Sync Server ===")
        print("Listening... (1 client at a time)")
        while True:
            try:
                conn, addr = server.accept()
                handle_client(conn, addr)
            except KeyboardInterrupt:
                print("\n[!] Server stopped")
                break


if __name__ == "__main__":
    main()