import socket
import threading
from tkinter import Tk, filedialog, Listbox, Button, Entry, Label
import os
import tkinter.simpledialog

class ClientApp:
    def __init__(self):
        self.client_socket = None
        self.download_dir = None  # To store the chosen download directory

        # Setting up the GUI for the client application. This will allow the user to interact with the client functionalities, such as connecting to the server, uploading files, and downloading files.
        self.root = Tk()
        self.root.title("Client GUI")
        self.root.geometry("500x400")

        # Adding labels and entry fields for server connection details
        Label(self.root, text="Server IP:").pack()
        self.ip_entry = Entry(self.root)
        self.ip_entry.pack()

        Label(self.root, text="Port:").pack()
        self.port_entry = Entry(self.root)
        self.port_entry.pack()

        # Adding a label and entry for the client name, which is a unique identifier for each client
        Label(self.root, text="Client Name:").pack()
        self.name_entry = Entry(self.root)
        self.name_entry.pack()

        # Button to establish a connection with the server
        self.connect_button = Button(self.root, text="Connect", command=self.connect_to_server)
        self.connect_button.pack()

        # Button for the user to select a directory where downloaded files will be saved
        self.select_download_dir_button = Button(self.root, text="Select Download Directory", command=self.set_download_directory)
        self.select_download_dir_button.pack()

        # A listbox to display the responses and updates from the server, such as successful uploads or errors
        self.listbox = Listbox(self.root, width=80)
        self.listbox.pack()

        # Button to upload files to the server. This allows the user to select a file from their system and send it to the server.
        self.upload_button = Button(self.root, text="Upload File", command=self.upload_file)
        self.upload_button.pack()

        # Button to list the files currently available on the server. The user will be able to view all uploaded files.
        self.list_button = Button(self.root, text="List Files", command=self.list_files)
        self.list_button.pack()

        # Button to download files from the server. The user can specify the file and owner to retrieve the file.
        self.download_button = Button(self.root, text="Download File", command=self.download_file)
        self.download_button.pack()

        # Button to delete files from the server. The user can specify a file to be removed.
        self.delete_button = Button(self.root, text="Delete File", command=self.delete_file)
        self.delete_button.pack()

        self.root.mainloop()


    def connect_to_server(self):
        # This function is responsible for connecting to the server.
        # It retrieves the server IP, port, and client name from the input fields in the GUI.
        ip = self.ip_entry.get()
        port = int(self.port_entry.get())
        name = self.name_entry.get()

        # Create a socket to establish a connection with the server
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((ip, port))
        self.client_socket.send(name.encode('utf-8'))

        threading.Thread(target=self.receive_from_server).start()

    def upload_file(self):
        # This function allows the client to upload a file to the server.
        # It first prompts the user to select a file using a file dialog. Once a file is selected,
        # it sends the file name and size to the server, followed by the file's content.

        filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if filepath:
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            self.client_socket.send(f"UPLOAD {filename}".encode('utf-8'))
            self.client_socket.send(str(file_size).encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')

            if response != "SIZE_RECEIVED":
                self.listbox.insert("end", f"ERROR: Server did not acknowledge file size for '{filename}'.")
                return

            try:
                with open(filepath, 'rb') as file:
                    while (chunk := file.read(1024)):
                        self.client_socket.send(chunk)
                self.listbox.insert("end", f"Uploaded file: {filename}")
            except Exception as e:
                self.listbox.insert("end", f"ERROR uploading file: {e}")


    def list_files(self):
        # Sends a request to the server to retrieve a list of available files
        # The server will respond with a list of files, which will be displayed in the listbox
        self.client_socket.send("LIST".encode('utf-8'))


    def set_download_directory(self):
        """Allow the user to select a download directory."""
        self.download_dir = filedialog.askdirectory()
        if self.download_dir:
            self.listbox.insert("end", f"Download directory set to: {self.download_dir}")


    def download_file(self):
        # This function handles downloading files from the server. The user must specify the owner of the file
        # and the file name. The file will be saved in the directory set by the user.
        if not self.download_dir:
            self.listbox.insert("end", "ERROR: Download directory not set.")
            return

        owner = self.simple_popup("Enter Owner's Name", "Owner")
        if not owner:
            self.listbox.insert("end", "ERROR: Owner name cannot be empty.")
            return

        # Validate owner with server
        self.client_socket.send(f"CHECK_OWNER {owner}".encode('utf-8'))
        response = self.client_socket.recv(1024).decode('utf-8')
        if response.startswith("ERROR:"):
            self.listbox.insert("end", response)
            return

        # Ask for file name
        filename = self.simple_popup("Enter Filename", "Filename")
        if not filename:
            self.listbox.insert("end", "ERROR: Filename cannot be empty.")
            return

        self.client_socket.send(f"DOWNLOAD {owner} {filename}".encode('utf-8'))
        filepath = os.path.join(self.download_dir, filename)

        try:
            # Receive file size
            file_size = int(self.client_socket.recv(1024).decode('utf-8'))
            self.client_socket.send("SIZE_RECEIVED".encode('utf-8'))

            # Download file in chunks
            with open(filepath, 'wb') as file:
                received_size = 0
                while received_size < file_size:
                    data = self.client_socket.recv(1024)
                    if not data:
                        break
                    file.write(data)
                    received_size += len(data)

            if received_size == file_size:
                self.listbox.insert("end", f"File '{filename}' downloaded successfully to {self.download_dir}")
            else:
                self.listbox.insert("end", f"ERROR: Incomplete file download for '{filename}'.")
                os.remove(filepath)  # Clean up incomplete file
        except Exception as e:
            self.listbox.insert("end", f"ERROR downloading file: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)  # Clean up incomplete file





    def delete_file(self):
        # This function allows the user to delete a file on the server.
        # The user will be prompted to enter the name of the file to delete.
        filename = self.simple_popup("Enter Filename to Delete", "Filename")
        if filename:
            self.client_socket.send(f"DELETE {filename}".encode('utf-8'))

    def simple_popup(self, title, prompt):
        # Helper function to display a popup dialog for user input
        return tkinter.simpledialog.askstring(title, prompt)

    def receive_from_server(self):
        # Continuously listen for messages from the server in a separate thread
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    self.listbox.insert("end", message)
            except Exception as e:
                self.listbox.insert("end", f"ERROR receiving message: {e}")
                break

if __name__ == "__main__":
    ClientApp()
