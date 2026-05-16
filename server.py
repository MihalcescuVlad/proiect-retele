import socket
import threading
import json
import uuid

HOST = "0.0.0.0"
PORT = 5000

clients = []
keys = {}
pending_requests = {}

lock = threading.Lock()


def send_json(client_socket, message):
    data = json.dumps(message) + "\n"
    client_socket.sendall(data.encode("utf-8"))


def broadcast(message):
    with lock:
        for client in clients:
            try:
                send_json(client, message)
            except:
                pass


def handle_publish(client_socket, message):
    key = message.get("key")

    if key is None:
        send_json(client_socket, {
            "type": "ERROR",
            "message": "Lipseste cheia."
        })
        return

    with lock:
        if key in keys:
            send_json(client_socket, {
                "type": "ERROR",
                "message": f"Cheia '{key}' exista deja."
            })
            return

        keys[key] = client_socket

    send_json(client_socket, {
        "type": "PUBLISH_OK",
        "key": key
    })

    broadcast({
        "type": "KEY_ADDED",
        "key": key
    })


def handle_get(client_socket, message):
    key = message.get("key")

    if key is None:
        send_json(client_socket, {
            "type": "ERROR",
            "message": "Lipseste cheia."
        })
        return

    with lock:
        if key not in keys:
            send_json(client_socket, {
                "type": "ERROR",
                "message": f"Cheia '{key}' nu exista."
            })
            return

        owner_socket = keys[key]
        request_id = str(uuid.uuid4())

        pending_requests[request_id] = {
            "requester": client_socket,
            "key": key
        }

    send_json(owner_socket, {
        "type": "SEND_OBJECT",
        "key": key,
        "request_id": request_id
    })


def handle_object_data(client_socket, message):
    request_id = message.get("request_id")
    key = message.get("key")
    data = message.get("data")

    if request_id is None or key is None:
        send_json(client_socket, {
            "type": "ERROR",
            "message": "Mesaj OBJECT_DATA invalid."
        })
        return

    with lock:
        if request_id not in pending_requests:
            send_json(client_socket, {
                "type": "ERROR",
                "message": "Cerere inexistenta sau expirata."
            })
            return

        pending = pending_requests[request_id]
        requester_socket = pending["requester"]

        del pending_requests[request_id]

    send_json(requester_socket, {
        "type": "GET_RESULT",
        "key": key,
        "data": data
    })


def handle_delete(client_socket, message):
    key = message.get("key")

    if key is None:
        send_json(client_socket, {
            "type": "ERROR",
            "message": "Lipseste cheia."
        })
        return

    with lock:
        if key not in keys:
            send_json(client_socket, {
                "type": "ERROR",
                "message": f"Cheia '{key}' nu exista."
            })
            return

        if keys[key] != client_socket:
            send_json(client_socket, {
                "type": "ERROR",
                "message": "Nu poti sterge o cheie publicata de alt client."
            })
            return

        del keys[key]

    send_json(client_socket, {
        "type": "DELETE_OK",
        "key": key
    })

    broadcast({
        "type": "KEY_REMOVED",
        "key": key
    })


def cleanup_client_keys(client_socket):
    removed_keys = []

    with lock:
        for key, owner in list(keys.items()):
            if owner == client_socket:
                removed_keys.append(key)
                del keys[key]

    for key in removed_keys:
        broadcast({
            "type": "KEY_REMOVED",
            "key": key
        })

    if removed_keys:
        print(f"[CURATARE] Au fost sterse cheile: {removed_keys}")


def handle_client(client_socket, address):
    print(f"[CONECTAT] Client nou: {address}")

    with lock:
        clients.append(client_socket)
        current_keys = list(keys.keys())

    send_json(client_socket, {
        "type": "KEY_LIST",
        "keys": current_keys
    })

    try:
        while True:
            data = client_socket.recv(4096)

            if not data:
                break

            message_text = data.decode("utf-8").strip()
            print(f"[MESAJ de la {address}] {message_text}")

            try:
                message = json.loads(message_text)
            except json.JSONDecodeError:
                send_json(client_socket, {
                    "type": "ERROR",
                    "message": "Mesaj JSON invalid."
                })
                continue

            message_type = message.get("type")

            if message_type == "PUBLISH":
                handle_publish(client_socket, message)

            elif message_type == "GET":
                handle_get(client_socket, message)

            elif message_type == "OBJECT_DATA":
                handle_object_data(client_socket, message)

            elif message_type == "DELETE":
                handle_delete(client_socket, message)

            else:
                send_json(client_socket, {
                    "type": "ERROR",
                    "message": "Tip de mesaj necunoscut."
                })

    except ConnectionResetError:
        print(f"[DECONECTARE FORTATA] {address}")

    finally:
        cleanup_client_keys(client_socket)

        with lock:
            if client_socket in clients:
                clients.remove(client_socket)

        client_socket.close()
        print(f"[DECONECTAT] {address}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"[SERVER PORNIT] Asculta pe portul {PORT}")

    while True:
        client_socket, address = server_socket.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(client_socket, address)
        )
        thread.start()


if __name__ == "__main__":
    start_server()