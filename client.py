import socket
import os
import threading

HOST = '127.0.0.1'
PORT = 8080
CLIENT_DIR = 'client_files'

os.makedirs(CLIENT_DIR, exist_ok=True)
upload_ready = threading.Event()

def send(sock, msg: str):
    sock.sendall((msg + '\n').encode())

def handle_list(parts):
    files = parts[1] if len(parts) > 1 else ''
    print(f"[Server Files] {files if files else 'Empty'}")
    print(">> ", end="", flush=True)

def handle_file(sock, filename, filesize, buffer):
    filepath = os.path.join(CLIENT_DIR, filename)
    received = 0
    with open(filepath, 'wb') as f:
        if buffer:
            chunk = buffer[:filesize]
            f.write(chunk)
            received += len(chunk)
            buffer = buffer[len(chunk):]
        while received < filesize:
            chunk = sock.recv(min(4096, filesize - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)
    print(f"[+] Downloaded {filename}")
    print(">> ", end="", flush=True)
    return buffer

def handle_ok(parts):
    print(f"[OK] {parts[1]}")
    print(">> ", end="", flush=True)

def handle_error(parts):
    print(f"\n[ERROR] {parts[1]}")
    print(">> ", end="", flush=True)

def handle_bcast(parts):
    print(f"[BCAST] {parts[1]}")
    print(">> ", end="", flush=True)

def receive_loop(sock):
    buffer = b""
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data

            while b'\n' in buffer:
                line_bytes, buffer = buffer.split(b'\n', 1)
                line = line_bytes.decode(errors='ignore')
                parts = line.split('|')
                cmd = parts[0]
                if cmd == 'LIST_OUT':
                    handle_list(parts)
                elif cmd == 'FILE':
                    filename = parts[1]
                    filesize = int(parts[2])
                    buffer = handle_file(sock, filename, filesize, buffer)
                elif cmd == 'OK':
                    handle_ok(parts)
                elif cmd == 'ERROR':
                    handle_error(parts)
                elif cmd == 'BCAST':
                    handle_bcast(parts)
                elif cmd == 'READY':
                    upload_ready.set()
    except:
        pass

def handle_upload(sock, filename):
    filepath = os.path.join(CLIENT_DIR, filename)
    if not os.path.exists(filepath):
        print("[ERROR] File not found in client_files")
        return
    filesize = os.path.getsize(filepath)
    send(sock, f"/upload {filename} {filesize}")

    while True:
        data = sock.recv(4096).decode()
        if "READY" in data:
            break

    with open(filepath, 'rb') as f:
        sock.sendall(f.read())
    print(f"[+] Uploaded {filename}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((HOST, PORT))
        except ConnectionRefusedError:
            print("[!] Server not running")
            return

        print("=== Connected to Server ===")
        print("Commands: /list, /upload <file>, /download <file>, /msg <text>, /exit")
        threading.Thread(target=receive_loop, args=(sock,), daemon=True).start()
        try:
            while True:
                msg = input(">> ").strip()
                if not msg:
                    continue
                if msg == '/exit':
                    send(sock, "/exit")
                    break
                elif msg == '/list':
                    send(sock, "/list")
                elif msg.startswith('/upload'):
                    try:
                        _, filename = msg.split()
                        handle_upload(sock, filename)
                    except ValueError:
                        print("Usage: /upload <filename>")
                elif msg.startswith('/download'):
                    try:
                        _, filename = msg.split()
                        send(sock, f"/download {filename}")
                    except ValueError:
                        print("Usage: /download <filename>")
                elif msg.startswith('/msg'):
                    send(sock, msg) 
                else:
                    print("[ERROR] Unknown command")

        except KeyboardInterrupt:
            print("\n[!] Disconnecting...")
            try:
                send(sock, "/exit")
            except:
                pass
        finally:
            print("[!] Connection closed")

if __name__ == "__main__":
    main()