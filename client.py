import argparse
import json
import os
import socket
import threading


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

DEMO_OBJECTS = {
    "student": {
        "nume": "Popescu Ana",
        "grupa": "342C1",
        "an": 3,
        "activ": True
    },
    "sensor": {
        "device_id": "sensor-01",
        "temperatura": 22.7,
        "umiditate": 48,
        "unitate": "celsius"
    },
    "book": {
        "titlu": "Retele de calculatoare",
        "autor": "Andrew S. Tanenbaum",
        "capitole": ["Transport", "Aplicatie", "Securitate"]
    },
    "config": {
        "retry": 3,
        "timeout_secunde": 10,
        "mod": "demo"
    }
}


class MemoryObjectClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.send_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.running = True

        self.local_objects = {}
        self.published_keys = set()
        self.known_server_keys = set()

    def connect(self):
        self.socket.connect((self.host, self.port))
        listener = threading.Thread(target=self.listen_to_server, daemon=True)
        listener.start()

    def send_json(self, message):
        data = json.dumps(message) + "\n"
        try:
            with self.send_lock:
                self.socket.sendall(data.encode("utf-8"))
            return True
        except OSError as exc:
            self.running = False
            self.print_status(f"Nu pot trimite mesajul catre server: {exc}")
            return False

    def listen_to_server(self):
        buffer = ""

        while self.running:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break

                buffer += chunk.decode("utf-8")

                while "\n" in buffer:
                    message_text, buffer = buffer.split("\n", 1)
                    message_text = message_text.strip()
                    if not message_text:
                        continue

                    try:
                        message = json.loads(message_text)
                    except json.JSONDecodeError:
                        self.print_status("Serverul a trimis un mesaj JSON invalid.")
                        continue

                    self.handle_server_message(message)
            except OSError:
                break
            except Exception as exc:
                self.print_status(f"Eroare la citirea mesajelor de la server: {exc}")
                break

        if self.running:
            self.running = False
            self.print_status("Conexiunea cu serverul s-a inchis.")

    def handle_server_message(self, message):
        message_type = message.get("type")

        if message_type == "KEY_LIST":
            keys = set(message.get("keys", []))
            with self.state_lock:
                self.known_server_keys = keys
            self.print_status(f"Chei disponibile pe server: {self.format_keys(keys)}")

        elif message_type == "KEY_ADDED":
            key = message.get("key")
            if key:
                with self.state_lock:
                    self.known_server_keys.add(key)
                self.print_status(f"Cheie publicata: {key}")

        elif message_type == "KEY_REMOVED":
            key = message.get("key")
            if key:
                with self.state_lock:
                    self.known_server_keys.discard(key)
                    self.published_keys.discard(key)
                self.print_status(f"Cheie stearsa de pe server: {key}")

        elif message_type == "PUBLISH_OK":
            key = message.get("key")
            if key:
                with self.state_lock:
                    self.published_keys.add(key)
                    self.known_server_keys.add(key)
                self.print_status(f"Publicare reusita pentru cheia '{key}'.")

        elif message_type == "DELETE_OK":
            key = message.get("key")
            if key:
                with self.state_lock:
                    self.published_keys.discard(key)
                    self.known_server_keys.discard(key)
                    self.local_objects.pop(key, None)
                self.print_status(f"Cheia '{key}' a fost stearsa si local, si de pe server.")

        elif message_type == "GET_RESULT":
            key = message.get("key")
            data = message.get("data")
            self.print_status(f"Obiect primit pentru '{key}':")
            print(json.dumps(data, indent=2, ensure_ascii=False))

        elif message_type == "SEND_OBJECT":
            self.serve_object(message)

        elif message_type == "ERROR":
            self.print_status(f"Eroare server: {message.get('message', 'necunoscuta')}")

        else:
            self.print_status(f"Mesaj server: {message}")

    def serve_object(self, message):
        key = message.get("key")
        request_id = message.get("request_id")

        with self.state_lock:
            data = self.local_objects.get(key)

        self.send_json({
            "type": "OBJECT_DATA",
            "request_id": request_id,
            "key": key,
            "data": data
        })

        if data is None:
            self.print_status(f"Serverul a cerut '{key}', dar obiectul nu mai exista local.")
        else:
            self.print_status(f"Am trimis obiectul '{key}' catre server.")

    def publish(self, key, data):
        with self.state_lock:
            if key in self.known_server_keys:
                self.print_status(f"Cheia '{key}' exista deja pe server. Alege alta cheie.")
                return
            self.local_objects[key] = data

        if self.send_json({
            "type": "PUBLISH",
            "key": key,
            "data": data
        }):
            self.print_status(f"Se publica '{key}'...")

    def publish_demo(self, demo_name, key):
        if demo_name not in DEMO_OBJECTS:
            self.print_status(f"Demo necunoscut: {demo_name}")
            self.print_demo_objects()
            return

        self.publish(key, DEMO_OBJECTS[demo_name])

    def get_object(self, key):
        if self.send_json({
            "type": "GET",
            "key": key
        }):
            self.print_status(f"Se cere obiectul '{key}'...")

    def delete(self, key):
        if self.send_json({
            "type": "DELETE",
            "key": key
        }):
            self.print_status(f"Se sterge cheia '{key}'...")

    def close_gracefully(self):
        self.running = False
        try:
            self.socket.close()
        except OSError:
            pass

    def force_disconnect(self):
        print("Simulez o deconectare fortata. Procesul se inchide imediat.")
        os._exit(1)

    def command_loop(self):
        self.print_welcome()

        while self.running:
            try:
                command = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not command:
                continue

            if not self.handle_command(command):
                break

        self.close_gracefully()

    def handle_command(self, command):
        parts = command.split()
        action = parts[0].lower()

        if action in ("exit", "quit"):
            return False

        if action == "help":
            self.print_help()
            return True

        if action == "demos":
            self.print_demo_objects()
            return True

        if action in ("list", "keys"):
            self.print_server_keys()
            return True

        if action == "local":
            self.print_local_objects()
            return True

        if action == "show":
            if len(parts) != 2:
                self.print_status("Utilizare: show <cheie>")
                return True
            self.print_local_object(parts[1])
            return True

        if action == "publish":
            self.handle_publish_command(command)
            return True

        if action == "publish-demo":
            if len(parts) not in (2, 3):
                self.print_status("Utilizare: publish-demo <demo> [cheie]")
                return True
            demo_name = parts[1]
            key = parts[2] if len(parts) == 3 else demo_name
            self.publish_demo(demo_name, key)
            return True

        if action == "get":
            if len(parts) != 2:
                self.print_status("Utilizare: get <cheie>")
                return True
            self.get_object(parts[1])
            return True

        if action == "delete":
            if len(parts) != 2:
                self.print_status("Utilizare: delete <cheie>")
                return True
            self.delete(parts[1])
            return True

        if action in ("force-disconnect", "crash"):
            self.force_disconnect()

        self.print_status("Comanda necunoscuta. Scrie 'help' pentru lista de comenzi.")
        return True

    def handle_publish_command(self, command):
        parts = command.split(" ", 2)
        if len(parts) != 3:
            self.print_status('Utilizare: publish <cheie> {"camp":"valoare"}')
            return

        key = parts[1]
        object_text = parts[2]

        try:
            data = json.loads(object_text)
        except json.JSONDecodeError as exc:
            self.print_status(f"JSON invalid: {exc.msg}")
            self.print_status('Exemplu: publish obj1 {"nume":"test","valoare":123}')
            return

        self.publish(key, data)

    def print_welcome(self):
        print("Client pornit.")
        print(f"Conectat la {self.host}:{self.port}.")
        print("Scrie 'help' pentru comenzi sau 'demos' pentru obiecte demo.")

    def print_help(self):
        print()
        print("Comenzi disponibile:")
        print('  list                          Afiseaza cheile curente de pe server')
        print('  publish <cheie> <json>        Publica un obiect JSON')
        print('  publish-demo <demo> [cheie]   Publica un obiect demo predefinit')
        print('  get <cheie>                   Cere un obiect de la alt client')
        print('  delete <cheie>                Sterge cheia publicata de tine')
        print('  keys                          Alias pentru list')
        print('  local                         Afiseaza obiectele locale')
        print('  show <cheie>                  Afiseaza un obiect local')
        print('  demos                         Afiseaza obiectele demo')
        print('  force-disconnect              Simuleaza deconectare fortata')
        print('  exit                          Inchide clientul normal')
        print()
        print("Scenariu rapid:")
        print('  list')
        print('  publish obj1 {"nume":"test","valoare":123}')
        print('  get obj1')
        print('  delete obj1')
        print()
        print('Exemplu: publish obj1 {"nume":"test","valoare":123}')
        print('Exemplu: publish-demo sensor obj-senzor')
        print()

    def print_server_keys(self):
        with self.state_lock:
            keys = set(self.known_server_keys)
        self.print_status(f"Chei curente pe server: {self.format_keys(keys)}")

    def print_demo_objects(self):
        print()
        print("Obiecte demo disponibile:")
        for name, value in DEMO_OBJECTS.items():
            preview = json.dumps(value, ensure_ascii=False)
            print(f"  {name}: {preview}")
        print()
        print("Publicare rapida: publish-demo sensor obj1")
        print()

    def print_local_objects(self):
        with self.state_lock:
            objects = dict(self.local_objects)
            published = set(self.published_keys)

        if not objects:
            self.print_status("Nu exista obiecte locale.")
            return

        print()
        print("Obiecte locale:")
        for key in sorted(objects):
            marker = "publicat" if key in published else "nepublicat"
            print(f"  {key} ({marker})")
        print()

    def print_local_object(self, key):
        with self.state_lock:
            exists = key in self.local_objects
            data = self.local_objects.get(key)

        if not exists:
            self.print_status(f"Nu exista obiect local pentru cheia '{key}'.")
            return

        print(json.dumps(data, indent=2, ensure_ascii=False))

    @staticmethod
    def format_keys(keys):
        if not keys:
            return "(niciuna)"
        return ", ".join(sorted(keys))

    @staticmethod
    def print_status(message):
        print(f"\n[client] {message}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Client interactiv pentru partajarea obiectelor in memorie."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Adresa serverului.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Portul serverului.")
    return parser.parse_args()


def main():
    args = parse_args()
    client = MemoryObjectClient(args.host, args.port)

    try:
        client.connect()
    except OSError as exc:
        print(f"Nu ma pot conecta la serverul {args.host}:{args.port}: {exc}")
        return

    client.command_loop()


if __name__ == "__main__":
    main()
