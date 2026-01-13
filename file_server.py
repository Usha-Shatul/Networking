import socket
import threading
import os
import json
import time
import hashlib
from datetime import datetime

class FileServer:
    def __init__(self, host='localhost', port=8888, storage_dir='server_files'):
        self.host = host
        self.port = port
        self.storage_dir = storage_dir
        self.server_socket = None
        self.running = False

        # Create storage directory if it doesn't exist
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
            print(f"[SERVER] Created storage directory: {self.storage_dir}")

    def get_file_info(self, filename):
        """Get file information"""
        filepath = os.path.join(self.storage_dir, filename)
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            return {
                'name': filename,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'exists': True
            }
        return {'name': filename, 'exists': False}

    def list_files(self):
        """List all files in storage directory"""
        try:
            files = []
            for filename in os.listdir(self.storage_dir):
                filepath = os.path.join(self.storage_dir, filename)
                if os.path.isfile(filepath):
                    files.append(self.get_file_info(filename))
            return {'status': 'success', 'files': files}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def store_file(self, filename, file_data):
        """Store file to server"""
        try:
            filepath = os.path.join(self.storage_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(file_data)
            return {'status': 'success', 'message': f'File {filename} stored successfully', 'size': len(file_data)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def delete_file(self, filename):
        """Delete file from server"""
        try:
            filepath = os.path.join(self.storage_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return {'status': 'success', 'message': f'File {filename} deleted successfully'}
            else:
                return {'status': 'error', 'message': f'File {filename} not found'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_file(self, filename):
        """Get file data for download"""
        try:
            filepath = os.path.join(self.storage_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                return {'status': 'success', 'data': file_data, 'size': len(file_data)}
            else:
                return {'status': 'error', 'message': f'File {filename} not found'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def send_response(self, client_socket, response):
        """Send response to client"""
        try:
            response_json = json.dumps(response)
            response_bytes = response_json.encode('utf-8')

            # Send response length first
            length = len(response_bytes)
            client_socket.send(length.to_bytes(4, byteorder='big'))

            # Send response data
            client_socket.send(response_bytes)
        except Exception as e:
            print(f"[SERVER] Error sending response: {e}")

    def send_file_data(self, client_socket, file_data):
        """Send file data to client"""
        try:
            # Send file size first
            file_size = len(file_data)
            client_socket.send(file_size.to_bytes(8, byteorder='big'))

            # Send file data in chunks
            chunk_size = 4096
            for i in range(0, file_size, chunk_size):
                chunk = file_data[i:i + chunk_size]
                client_socket.send(chunk)
        except Exception as e:
            print(f"[SERVER] Error sending file data: {e}")

    def receive_file_data(self, client_socket):
        """Receive file data from client"""
        try:
            # Receive file size first
            size_bytes = client_socket.recv(8)
            if len(size_bytes) != 8:
                return None

            file_size = int.from_bytes(size_bytes, byteorder='big')

            # Receive file data
            file_data = b''
            while len(file_data) < file_size:
                chunk = client_socket.recv(min(4096, file_size - len(file_data)))
                if not chunk:
                    break
                file_data += chunk

            return file_data
        except Exception as e:
            print(f"[SERVER] Error receiving file data: {e}")
            return None

    def handle_client(self, client_socket, address):
        """Handle client requests"""
        print(f"[SERVER] Client connected from {address}")

        try:
            while True:
                # Receive request length
                length_bytes = client_socket.recv(4)
                if not length_bytes:
                    break

                request_length = int.from_bytes(length_bytes, byteorder='big')

                # Receive request data
                request_data = client_socket.recv(request_length)
                if not request_data:
                    break

                try:
                    request = json.loads(request_data.decode('utf-8'))
                    command = request.get('command', '')

                    print(f"[SERVER] Received command: {command} from {address}")

                    if command == 'LIST':
                        response = self.list_files()
                        self.send_response(client_socket, response)

                    elif command == 'UPLOAD':
                        filename = request.get('filename', '')
                        if filename:
                            file_data = self.receive_file_data(client_socket)
                            if file_data is not None:
                                response = self.store_file(filename, file_data)
                            else:
                                response = {'status': 'error', 'message': 'Failed to receive file data'}
                        else:
                            response = {'status': 'error', 'message': 'Filename not provided'}

                        self.send_response(client_socket, response)

                    elif command == 'DOWNLOAD':
                        filename = request.get('filename', '')
                        if filename:
                            result = self.get_file(filename)
                            if result['status'] == 'success':
                                # Send success response first
                                response = {'status': 'success', 'size': result['size']}
                                self.send_response(client_socket, response)
                                # Then send file data
                                self.send_file_data(client_socket, result['data'])
                            else:
                                self.send_response(client_socket, result)
                        else:
                            response = {'status': 'error', 'message': 'Filename not provided'}
                            self.send_response(client_socket, response)

                    elif command == 'DELETE':
                        filename = request.get('filename', '')
                        if filename:
                            response = self.delete_file(filename)
                        else:
                            response = {'status': 'error', 'message': 'Filename not provided'}

                        self.send_response(client_socket, response)

                    elif command == 'QUIT':
                        response = {'status': 'success', 'message': 'Goodbye!'}
                        self.send_response(client_socket, response)
                        break

                    else:
                        response = {'status': 'error', 'message': f'Unknown command: {command}'}
                        self.send_response(client_socket, response)

                except json.JSONDecodeError:
                    response = {'status': 'error', 'message': 'Invalid request format'}
                    self.send_response(client_socket, response)

        except Exception as e:
            print(f"[SERVER] Error handling client {address}: {e}")
        finally:
            client_socket.close()
            print(f"[SERVER] Client {address} disconnected")

    def start_server(self):
        """Start the file server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True

            print(f"[SERVER] File server started on {self.host}:{self.port}")
            print(f"[SERVER] Storage directory: {os.path.abspath(self.storage_dir)}")
            print("[SERVER] Waiting for clients...")

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except OSError:
                    break

        except Exception as e:
            print(f"[SERVER] Error starting server: {e}")
        finally:
            self.stop_server()

    def stop_server(self):
        """Stop the file server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("\n[SERVER] File server stopped")

if __name__ == "__main__":
    server = FileServer()
    try:
        server.start_server()
    except KeyboardInterrupt:
        server.stop_server()