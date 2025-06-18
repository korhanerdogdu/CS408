import socket
import threading
import os
from tkinter import Tk, filedialog, Listbox, Button, Entry, Label

class ServerApp:
    def __init__(self):
        # Initialization of server attributes
        self.server_socket = None # The main socket for server-client communication
        self.clients = {}  # {client_name: client_socket}
        self.files = {}  # {filename: owner_name}
        self.upload_dir = ""

        # Setting up the GUI for the server
        self.root = Tk()
        self.root.title("Server GUI")
        self.root.geometry("600x400")

        # Input field for specifying the port on which the server will listen
        Label(self.root, text="Port:").pack()
        self.port_entry = Entry(self.root)
        self.port_entry.pack()

        # Button to allow the server admin to select the directory for uploaded files
        self.select_dir_button = Button(self.root, text="Select Upload Directory", command=self.set_upload_directory)
        self.select_dir_button.pack()

        # Button to start the server and begin listening for client connections
        self.start_button = Button(self.root, text="Start Server", command=self.start_server)
        self.start_button.pack()

        # Listbox to display server logs and messages (e.g., connection details, errors)
        self.listbox = Listbox(self.root, width=80)
        self.listbox.pack()

        self.root.mainloop()

    def set_upload_directory(self):

        # This method allows the server admin to select a directory for storing uploaded files
        self.upload_dir = filedialog.askdirectory()
        self.log_message(f"Upload directory set to: {self.upload_dir}")

    def start_server(self):
        try:
            port = int(self.port_entry.get())
            if not self.upload_dir:
                self.log_message("ERROR: Upload directory not set!")
                return
            
            # Create a socket for the server to listen for incoming client connections
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(("", port))
            self.server_socket.listen(5)
            self.log_message(f"Server started on port {port}, waiting for connections...")

            threading.Thread(target=self.accept_clients).start()
        except Exception as e:
            self.log_message(f"ERROR: {e}")

    def accept_clients(self):
        # This method continuously accepts incoming client connections
        while True:
            client_socket, client_address = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket, client_address)).start()


    def handle_check_owner(self, client_socket, args):
        # Check if a specific owner has uploaded any files
        if len(args) < 1:
            client_socket.send("ERROR: No owner specified.".encode('utf-8'))
            self.log_message("ERROR: Client sent a CHECK_OWNER request without specifying an owner.")
            return

        owner = args[0]
        if any(owner == file_owner for file_owner in self.files.values()):
            client_socket.send("OWNER_VALID".encode('utf-8'))
        else:
            client_socket.send(f"ERROR: Owner '{owner}' not found.".encode('utf-8'))
            self.log_message(f"ERROR: Owner '{owner}' does not exist.")


    def handle_client(self, client_socket, client_address):
        try:
            client_name = client_socket.recv(1024).decode('utf-8')
            if client_name in self.clients:
                # Inform the new client and log the disconnection on the server
                client_socket.send("ERROR: Client name already in use.".encode('utf-8'))
                self.log_message(f"The new client '{client_name}' disconnected because the name is already in use.")
                client_socket.close()  # Disconnect only the new client
                return

            # Add the new client to the client dictionary
            self.clients[client_name] = client_socket
            self.log_message(f"Client '{client_name}' connected from {client_address}.")

            # Handle client commands
            while True:
                command = client_socket.recv(1024).decode('utf-8')
                if not command:
                    break

                command_parts = command.split(' ')
                cmd = command_parts[0]

                if cmd == "UPLOAD":
                    self.handle_upload(client_name, client_socket, command_parts[1:])
                elif cmd == "LIST":
                    self.handle_list(client_socket)
                elif cmd == "DELETE":
                    self.handle_delete(client_name, client_socket, command_parts[1:])
                elif cmd == "DOWNLOAD":
                    self.handle_download(client_socket, command_parts[1:])
                elif cmd == "CHECK_OWNER":
                    self.handle_check_owner(client_socket, command_parts[1:])
                else:
                    client_socket.send("ERROR: Unknown command.".encode('utf-8'))
        except Exception as e:
            self.log_message(f"ERROR with client '{client_name}': {e}")
        finally:
            # Ensure we only remove the client if it was successfully added
            if client_name in self.clients and self.clients[client_name] == client_socket:
                self.disconnect_client(client_name)
                self.log_message(f"The client named '{client_name}' is disconnected.")




    def handle_upload(self, client_name, client_socket, args):
        # Handle a file upload from a client
        filename = args[0]
        unique_filename = f"{client_name}_{filename}"
        filepath = os.path.join(self.upload_dir, unique_filename)

        try:
            # Receive the file size first
            file_size = int(client_socket.recv(1024).decode('utf-8'))
            client_socket.send("SIZE_RECEIVED".encode('utf-8'))

            with open(filepath, 'wb') as file:
                received_size = 0
                while received_size < file_size:
                    data = client_socket.recv(1024)
                    file.write(data)
                    received_size += len(data)

            self.files[unique_filename] = client_name
            client_socket.send(f"File {filename} uploaded successfully.".encode('utf-8'))
            self.log_message(f"File '{filename}' uploaded by '{client_name}'.")
        except Exception as e:
            client_socket.send(f"ERROR: {e}".encode('utf-8'))
            self.log_message(f"ERROR during file upload: {e}")


    def handle_list(self, client_socket):
        # Send a list of available files to the client
        file_list = "\n".join([f"{file.split('_', 1)[1]} by {owner} " for file, owner in self.files.items()])
        client_socket.send(file_list.encode('utf-8'))
        self.log_message("Sent file list to a client.")

    def handle_delete(self, client_name, client_socket, args):
        # Handle a request to delete a file
        filename = args[0]
        unique_filename = f"{client_name}_{filename}"
        if unique_filename not in self.files:
            client_socket.send("ERROR: File not found or not owned by you.".encode('utf-8'))
            return

        filepath = os.path.join(self.upload_dir, unique_filename)
        os.remove(filepath)
        del self.files[unique_filename]
        client_socket.send(f"File {filename} deleted successfully.".encode('utf-8'))
        self.log_message(f"File '{filename}' deleted by '{client_name}'.")

    def handle_download(self, client_socket, args):
        # Handle a file download request
        if len(args) < 2:
            client_socket.send("ERROR: Invalid download request format.".encode('utf-8'))
            self.log_message("ERROR: Client sent an invalid download request.")
            return

        owner, filename = args
        unique_filename = f"{owner}_{filename}"

        if unique_filename not in self.files:
            client_socket.send(f"ERROR: File '{filename}' not found for owner '{owner}'.".encode('utf-8'))
            self.log_message(f"ERROR: File '{filename}' not found for owner '{owner}'.")
            return

        filepath = os.path.join(self.upload_dir, unique_filename)
        try:
            # Get file size and notify the client
            file_size = os.path.getsize(filepath)
            client_socket.send(str(file_size).encode('utf-8'))
            response = client_socket.recv(1024).decode('utf-8')
            if response != "SIZE_RECEIVED":
                self.log_message(f"ERROR: Client did not acknowledge file size for '{filename}'.")
                return

            # Stream file in chunks
            with open(filepath, 'rb') as file:
                while (chunk := file.read(1024)):
                    client_socket.send(chunk)
            client_socket.send("EOF".encode('utf-8'))  # End of file marker
            self.log_message(f"File '{filename}' sent to client.")

            # Notify uploader if connected
            if owner in self.clients:
                self.clients[owner].send(f"Your file '{filename}' was downloaded.".encode('utf-8'))
                self.log_message(f"Notified uploader '{owner}' about the download of '{filename}'.")
        except Exception as e:
            client_socket.send(f"ERROR: Unable to download file: {e}".encode('utf-8'))
            self.log_message(f"ERROR during file download: {e}")





    def disconnect_client(self, client_name):
        # Disconnect a client and remove them from the clients dictionary
        if client_name in self.clients:
            self.clients[client_name].close()
            del self.clients[client_name]
            self.log_message(f"Client '{client_name}' disconnected.")

    def log_message(self, message):
        # Add a message to the server's log in the GUI
        self.listbox.insert("end", message)
        self.listbox.see("end")

if __name__ == "__main__":
    ServerApp()