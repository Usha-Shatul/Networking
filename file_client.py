import socket
import os
import json
import sys

class FileClient:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.client_socket = None
        self.connected = False

    def connect(self):
        """Connect to file server"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            self.connected = True
            print(f"[CLIENT] Connected to file server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[CLIENT] Error connecting to server: {e}")
            return False

    def disconnect(self):
        """Disconnect from server"""
        if self.connected and self.client_socket:
            try:
                # Send quit command
                request = {'command': 'QUIT'}
                self.send_request(request)
                response = self.receive_response()

                self.client_socket.close()
                self.connected = False
                print("[CLIENT] Disconnected from server")
            except:
                pass

    def send_request(self, request):
        """Send request to server"""
        try:
            request_json = json.dumps(request)
            request_bytes = request_json.encode('utf-8')

            # Send request length first
            length = len(request_bytes)
            self.client_socket.send(length.to_bytes(4, byteorder='big'))

            # Send request data
            self.client_socket.send(request_bytes)
        except Exception as e:
            print(f"[CLIENT] Error sending request: {e}")
            raise

    def receive_response(self):
        """Receive response from server"""
        try:
            # Receive response length
            length_bytes = self.client_socket.recv(4)
            if len(length_bytes) != 4:
                return None

            response_length = int.from_bytes(length_bytes, byteorder='big')

            # Receive response data
            response_data = self.client_socket.recv(response_length)
            if not response_data:
                return None

            return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            print(f"[CLIENT] Error receiving response: {e}")
            return None

    def send_file_data(self, filepath):
        """Send file data to server"""
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            # Send file size first
            file_size = len(file_data)
            self.client_socket.send(file_size.to_bytes(8, byteorder='big'))

            # Send file data in chunks
            chunk_size = 4096
            for i in range(0, file_size, chunk_size):
                chunk = file_data[i:i + chunk_size]
                self.client_socket.send(chunk)

            return True
        except Exception as e:
            print(f"[CLIENT] Error sending file: {e}")
            return False

    def receive_file_data(self, filepath):
        """Receive file data from server"""
        try:
            # Receive file size first
            size_bytes = self.client_socket.recv(8)
            if len(size_bytes) != 8:
                return False

            file_size = int.from_bytes(size_bytes, byteorder='big')

            # Receive file data
            with open(filepath, 'wb') as f:
                received = 0
                while received < file_size:
                    chunk = self.client_socket.recv(min(4096, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

            return received == file_size
        except Exception as e:
            print(f"[CLIENT] Error receiving file: {e}")
            return False

    def list_files(self):
        """List files on server"""
        try:
            request = {'command': 'LIST'}
            self.send_request(request)
            response = self.receive_response()

            if response and response.get('status') == 'success':
                files = response.get('files', [])
                if files:
                    print("\n=== Files on Server ===")
                    print(f"{'Filename':<30} {'Size':<15} {'Modified':<20}")
                    print("-" * 65)
                    for file_info in files:
                        name = file_info['name']
                        size = self.format_file_size(file_info['size'])
                        modified = file_info['modified']
                        print(f"{name:<30} {size:<15} {modified:<20}")
                    print(f"\nTotal files: {len(files)}")
                else:
                    print("\n[INFO] No files found on server")
            else:
                print(f"[ERROR] {response.get('message', 'Unknown error')}")

        except Exception as e:
            print(f"[CLIENT] Error listing files: {e}")

    def upload_file(self, filepath):
        """Upload file to server"""
        try:
            if not os.path.exists(filepath):
                print(f"[ERROR] File not found: {filepath}")
                return

            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)

            print(f"[CLIENT] Uploading {filename} ({self.format_file_size(file_size)})...")

            # Send upload request
            request = {'command': 'UPLOAD', 'filename': filename}
            self.send_request(request)

            # Send file data
            if self.send_file_data(filepath):
                # Receive response
                response = self.receive_response()
                if response and response.get('status') == 'success':
                    print(f"[SUCCESS] File uploaded successfully: {filename}")
                else:
                    print(f"[ERROR] Upload failed: {response.get('message', 'Unknown error')}")
            else:
                print("[ERROR] Failed to send file data")

        except Exception as e:
            print(f"[CLIENT] Error uploading file: {e}")

    def download_file(self, filename, save_path=None):
        """Download file from server"""
        try:
            if save_path is None:
                save_path = filename

            print(f"[CLIENT] Downloading {filename}...")

            # Send download request
            request = {'command': 'DOWNLOAD', 'filename': filename}
            self.send_request(request)

            # Receive response
            response = self.receive_response()
            if response and response.get('status') == 'success':
                file_size = response.get('size', 0)
                print(f"[CLIENT] File size: {self.format_file_size(file_size)}")

                # Receive file data
                if self.receive_file_data(save_path):
                    print(f"[SUCCESS] File downloaded: {save_path}")
                else:
                    print("[ERROR] Failed to receive file data")
            else:
                print(f"[ERROR] Download failed: {response.get('message', 'Unknown error')}")

        except Exception as e:
            print(f"[CLIENT] Error downloading file: {e}")

    def delete_file(self, filename):
        """Delete file from server"""
        try:
            print(f"[CLIENT] Deleting {filename}...")

            request = {'command': 'DELETE', 'filename': filename}
            self.send_request(request)
            response = self.receive_response()

            if response and response.get('status') == 'success':
                print(f"[SUCCESS] File deleted: {filename}")
            else:
                print(f"[ERROR] Delete failed: {response.get('message', 'Unknown error')}")

        except Exception as e:
            print(f"[CLIENT] Error deleting file: {e}")

    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"

    def run_interactive(self):
        """Run interactive client"""
        if not self.connect():
            return

        print("\n=== File Client Interactive Mode ===")
        print("Commands:")
        print("  list                    - List files on server")
        print("  upload <filepath>       - Upload file to server")
        print("  download <filename>     - Download file from server")
        print("  delete <filename>       - Delete file from server")
        print("  quit                    - Exit client")
        print("-" * 50)

        try:
            while self.connected:
                command = input("\nfile_client> ").strip().split()

                if not command:
                    continue

                cmd = command[0].lower()

                if cmd == 'list':
                    self.list_files()

                elif cmd == 'upload':
                    if len(command) > 1:
                        self.upload_file(command[1])
                    else:
                        print("[ERROR] Usage: upload <filepath>")

                elif cmd == 'download':
                    if len(command) > 1:
                        self.download_file(command[1])
                    else:
                        print("[ERROR] Usage: download <filename>")

                elif cmd == 'delete':
                    if len(command) > 1:
                        confirm = input(f"Are you sure you want to delete '{command[1]}'? (y/N): ")
                        if confirm.lower() == 'y':
                            self.delete_file(command[1])
                        else:
                            print("[INFO] Delete cancelled")
                    else:
                        print("[ERROR] Usage: delete <filename>")

                elif cmd == 'quit':
                    break

                elif cmd == 'help':
                    print("\nCommands:")
                    print("  list                    - List files on server")
                    print("  upload <filepath>       - Upload file to server")
                    print("  download <filename>     - Download file from server")
                    print("  delete <filename>       - Delete file from server")
                    print("  quit                    - Exit client")

                else:
                    print(f"[ERROR] Unknown command: {cmd}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\n[CLIENT] Interrupted by user")
        finally:
            self.disconnect()

if __name__ == "__main__":
    client = FileClient()
    client.run_interactive()
