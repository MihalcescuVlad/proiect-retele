import socket
import json
import threading

HOST = "127.0.0.1"
PORT = 5000

local_objects = {}


def send_json(client_socket, message):
    client_socket.sendall((json.dumps(message) + "\n").encode("utf-8"))


def listen_to_server(client_socket):
    while True:
        try:
            data = client_socket.recv(4096)

            if not data:
                break

            messages = data.decode("utf-8").strip().split("\n")

            for message_text in messages:
                if message_text:
                    message = json.loads(message_text)
                    print("[SERVER]", message)

                    if message.get("type") == "SEND_OBJECT":
                        key = message.get("key")
                        request_id = message.get("request_id")

                        if key in local_objects:
                            response = {
                                "type": "OBJECT_DATA",
                                "request_id": request_id,
                                "key": key,
                                "data": local_objects[key]
                            }

                            send_json(client_socket, response)
                        else:
                            response = {
                                "type": "OBJECT_DATA",
                                "request_id": request_id,
                                "key": key,
                                "data": None
                            }

                            send_json(client_socket, response)

        except:
            break


client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))

thread = threading.Thread(
    target=listen_to_server,
    args=(client_socket,),
    daemon=True
)
thread.start()

while True:
    command = input("> ")

    if command == "exit":
        break

    if command.startswith("publish "):
        parts = command.split(" ", 2)

        if len(parts) < 3:
            print("Comanda corecta: publish cheie obiect_json")
            continue

        key = parts[1]

        try:
            data = json.loads(parts[2])
        except json.JSONDecodeError:
            print("Obiectul trebuie sa fie JSON valid.")
            continue

        local_objects[key] = data

        message = {
            "type": "PUBLISH",
            "key": key,
            "data": data
        }

        send_json(client_socket, message)

    elif command.startswith("get "):
        parts = command.split(" ", 1)

        if len(parts) < 2:
            print("Comanda corecta: get cheie")
            continue

        key = parts[1]

        message = {
            "type": "GET",
            "key": key
        }

        send_json(client_socket, message)

    elif command.startswith("delete "):
        parts = command.split(" ", 1)

        if len(parts) < 2:
            print("Comanda corecta: delete cheie")
            continue

        key = parts[1]

        if key in local_objects:
            del local_objects[key]

        message = {
            "type": "DELETE",
            "key": key
        }

        send_json(client_socket, message)

    else:
        print("Comanda necunoscuta.")
        print("Comenzi disponibile:")
        print("publish obj1 {\"nume\":\"test\",\"valoare\":123}")
        print("get obj1")
        print("delete obj1")
        print("exit")

client_socket.close()