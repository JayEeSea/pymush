def handle_command(command, client_socket, clients, channels, channel_config_file, player_rooms, rooms):
    if command.startswith('/quit'):
        client_socket.send(b'Disconnecting...\n')
        clients.remove(client_socket)
        client_socket.close()
    elif command.startswith('/who'):
        users = [f'Client {i+1}' for i in range(len(clients))]
        client_socket.send(f'Connected users: {", ".join(users)}\n'.encode('utf-8'))
    elif command.startswith('/addchannel '):
        # Add a new channel
        parts = command.split(' ', 2)
        if len(parts) < 3:
            client_socket.send(b'Usage: /addchannel <channel_name> <display_name>\n')
            return
        channel_name = parts[1].lower()
        display_name = parts[2]
        
        if channel_name in channels:
            client_socket.send(b'Channel already exists.\n')
            return
        
        # Add the channel to the in-memory structure
        channels[channel_name] = []
        
        # Update the channel config file
        with open(channel_config_file, 'a') as config_file:
            config_file.write(f'{channel_name} = {display_name}\n')
        
        client_socket.send(f'Channel "{display_name}" added successfully.\n'.encode('utf-8'))
    elif command.startswith('/listchannels'):
        # List all chat channels
        channel_list = [f'{name} ({display_name})' for name, display_name in channels.items()]
        client_socket.send(f'Available channels: {", ".join(channel_list)}\n'.encode('utf-8'))
    elif command.startswith('/removechannel '):
        # Remove a channel
        parts = command.split(' ', 1)
        if len(parts) < 2:
            client_socket.send(b'Usage: /removechannel <channel_name>\n')
            return
        channel_name = parts[1].lower()
        
        if channel_name not in channels:
            client_socket.send(b'Channel does not exist.\n')
            return
        
        # Remove the channel from the in-memory structure
        del channels[channel_name]
        
        # Update the channel config file
        with open(channel_config_file, 'r') as config_file:
            lines = config_file.readlines()
        with open(channel_config_file, 'w') as config_file:
            for line in lines:
                if not line.startswith(f'{channel_name} = '):
                    config_file.write(line)
        
        client_socket.send(f'Channel "{channel_name}" removed successfully.\n'.encode('utf-8'))
    elif command.startswith('/look'):
        # Look around the current room
        room_id = player_rooms.get(client_socket, "1")
        room = rooms.get(room_id)
        if room:
            client_socket.send(f'You are in {room["name"]}.\n{room["description"]}\n'.encode('utf-8'))
            if room["exits"]:
                exits = ', '.join(room["exits"].keys())
                client_socket.send(f'Exits: {exits}\n'.encode('utf-8'))
        else:
            client_socket.send(b'You are in an unknown place.\n')
    elif command.startswith('/go '):
        # Move to a new room
        parts = command.split(' ', 1)
        if len(parts) < 2:
            client_socket.send(b'Usage: /go <direction>\n')
            return
        direction = parts[1].lower()
        current_room_id = player_rooms.get(client_socket, "1")
        current_room = rooms.get(current_room_id)
        if current_room and direction in current_room["exits"]:
            new_room_id = current_room["exits"][direction]
            player_rooms[client_socket] = new_room_id
            new_room = rooms.get(new_room_id)
            client_socket.send(f'You move {direction} and arrive in {new_room["name"]}.\n{new_room["description"]}\n'.encode('utf-8'))
        else:
            client_socket.send(b'You cannot go that way.\n')
    else:
        client_socket.send(b'Unknown command.\n')
