import socket
import threading
import mysql.connector
import hashlib
import os
import configparser
import logging
from logging.handlers import RotatingFileHandler
from mush_commands import handle_command

class SimpleMUSHServer:
    def __init__(self, config_file='config.ini', channel_config_file='channel_config.ini'):
        config = configparser.ConfigParser()
        config.read(config_file)

        # Load server configuration
        self.host = config['SERVER']['Host']
        self.port = int(config['SERVER']['Port'])
        self.server_name = config['SERVER']['Name']
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.channels = {}  # Dictionary to hold channel members
        self.db = mysql.connector.connect(
            host=config['MYSQL']['Host'],
            user=config['MYSQL']['User'],
            password=config['MYSQL']['Password'],
            database=config['MYSQL']['Database']
        )

        # Load channel configuration
        channel_config = configparser.ConfigParser()
        channel_config.read(channel_config_file)
        self.channel_names = {key.lower(): value for key, value in channel_config['CHANNELS'].items()}
        for channel in self.channel_names.keys():
            self.channels[channel] = []

        # Logging setup
        if config['LOGGING'].getboolean('Enable'):
            log_file_path = config['LOGGING']['LogFilePath']
            log_level = getattr(logging, config['LOGGING']['LogLevel'].upper(), logging.INFO)
            max_log_file_size = int(config['LOGGING']['MaxLogFileSize'][:-2]) * 1024 * 1024  # Convert MB to bytes
            backup_count = int(config['LOGGING']['BackupCount'])

            logging.basicConfig(level=log_level)
            handler = RotatingFileHandler(log_file_path, maxBytes=max_log_file_size, backupCount=backup_count)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(handler)
            print(f"[INFO] Logging enabled. Logs will be saved to {log_file_path}")
        else:
            print("[INFO] Logging is disabled.")
        
    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logging.info(f'{self.server_name} started on {self.host}:{self.port}')
        print(f'[INFO] {self.server_name} started on {self.host}:{self.port}')
        
        while True:
            client_socket, client_address = self.server_socket.accept()
            logging.info(f'Connection from {client_address}')
            print(f'[INFO] Connection from {client_address}')
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        
    def handle_client(self, client_socket):
        client_socket.send(f'Welcome to {self.server_name}!\nWould you like to (1) Login or (2) Create a new character?\n'.encode('utf-8'))
        while True:
            option = client_socket.recv(1024).decode('utf-8').strip()
            if option == '1':
                if self.authenticate(client_socket):
                    break
                else:
                    client_socket.send(b'Authentication failed. Please try again.\n')
                    logging.warning(f'Failed authentication attempt from client {client_socket.getpeername()}')
            elif option == '2':
                if self.create_character(client_socket):
                    client_socket.send(b'Character creation successful! Please login.\n')
                else:
                    client_socket.send(b'Character creation failed. Please try again.\n')
            else:
                client_socket.send(b'Invalid option. Please enter 1 to Login or 2 to Create a new character.\n')
        
        client_socket.send(b'Authentication successful!\n')
        self.clients.append(client_socket)
        logging.info(f'Client {client_socket.getpeername()} authenticated successfully')
        
        while True:
            try:
                message = client_socket.recv(1024).decode('utf-8').strip()
                if not message:
                    break
                if message.startswith('/'):
                    logging.debug(f'Received command from client {client_socket.getpeername()}: {message}')
                    handle_command(message, client_socket, self.clients)
                elif message.startswith('+'):
                    self.handle_channel_message(message, client_socket)
                else:
                    self.broadcast(message, client_socket)
            except ConnectionResetError:
                break
        
        logging.info(f'Client {client_socket.getpeername()} disconnected')
        print('Client disconnected')
        self.clients.remove(client_socket)
        client_socket.close()
        
    def authenticate(self, client_socket):
        client_socket.send(b'Username: ')
        username = client_socket.recv(1024).decode('utf-8').strip()
        client_socket.send(b'Password: ')
        password = client_socket.recv(1024).decode('utf-8').strip()
        
        cursor = self.db.cursor()
        cursor.execute("SELECT salt, password_hash FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        if result:
            salt, stored_hash = result
            hashed_password = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
            if hashed_password == stored_hash:
                return True
        return False

    def create_character(self, client_socket):
        client_socket.send(b'Choose a character name: ')
        username = client_socket.recv(1024).decode('utf-8').strip()
        client_socket.send(b'Enter a password: ')
        password = client_socket.recv(1024).decode('utf-8').strip()
        client_socket.send(b'Enter your email address: ')
        email = client_socket.recv(1024).decode('utf-8').strip()

        salt = os.urandom(16).hex()
        hashed_password = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

        cursor = self.db.cursor()
        try:
            cursor.execute("INSERT INTO users (username, salt, password_hash, email) VALUES (%s, %s, %s, %s)",
                           (username, salt, hashed_password, email))
            self.db.commit()
            logging.info(f'New character created: {username}')
            return True
        except mysql.connector.Error as err:
            logging.error(f'Error creating character: {err}')
            return False
        
    def handle_channel_message(self, message, client_socket):
        parts = message.split(' ', 1)
        if len(parts) < 2:
            client_socket.send(b'Invalid channel message format. Use +channel_name message.\n')
            return

        channel_name = parts[0][1:].lower()
        message_content = parts[1]
        
        if channel_name not in self.channels:
            client_socket.send(b'Channel does not exist.\n')
            return
        
        if client_socket not in self.channels[channel_name]:
            self.channels[channel_name].append(client_socket)

        sender_username = self.get_username(client_socket)
        formatted_message = f'<{self.channel_names[channel_name]}> {sender_username} says, "{message_content}"\n'
        logging.info(f'Channel message on {channel_name} from {sender_username}: {message_content}')
        for client in self.channels[channel_name]:
            try:
                client.send(formatted_message.encode('utf-8'))
            except BrokenPipeError:
                continue
        
    def get_username(self, client_socket):
        cursor = self.db.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (id(client_socket),))
        result = cursor.fetchone()
        if result:
            return result[0]
        return 'Unknown'

    def broadcast(self, message, sender_socket):
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.send(message.encode('utf-8'))
                except BrokenPipeError:
                    continue
        
if __name__ == '__main__':
    server = SimpleMUSHServer()
    server.start()