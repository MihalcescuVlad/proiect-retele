import argparse
import json
import socket
import struct
import subprocess
import sys
import threading
import time


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEMO_OBJECTS = {
    "obj1": {"nume": "test", "valoare": 123},
    "obj2": {
        "nume": "obiect-mare",
        "payload": "x" * 12000
    }
}


def format_for_log(message):
    text = json.dumps(message, ensure_ascii=False)
    if len(text) <= 500:
        return text
    return text[:500] + "... [mesaj trunchiat in log]"


class DemoClient:
    def __init__(self, name, host, port):
        self.name = name
        self.host = host
        self.port = port
        self.socket = socket.create_connection((host, port), timeout=3)
        self.socket.settimeout(0.5)
        self.objects = {}
        self.messages = []
        self.lock = threading.Lock()
        self.running = True
        self.listener = threading.Thread(target=self.listen, daemon=True)
        self.listener.start()

    def listen(self):
        buffer = ""

        while self.running:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break

                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    raw_message, buffer = buffer.split("\n", 1)
                    raw_message = raw_message.strip()
                    if not raw_message:
                        continue

                    message = json.loads(raw_message)
                    with self.lock:
                        self.messages.append(message)

                    print(f"SERVER -> {self.name}: {format_for_log(message)}")

                    if message.get("type") == "SEND_OBJECT":
                        self.send_object(message)
            except socket.timeout:
                continue
            except OSError:
                break

    def send(self, message):
        print(f"{self.name} -> SERVER: {format_for_log(message)}")
        self.socket.sendall((json.dumps(message) + "\n").encode("utf-8"))

    def send_object(self, message):
        key = message.get("key")
        request_id = message.get("request_id")
        self.send({
            "type": "OBJECT_DATA",
            "request_id": request_id,
            "key": key,
            "data": self.objects.get(key)
        })

    def publish(self, key, data):
        self.objects[key] = data
        self.send({
            "type": "PUBLISH",
            "key": key,
            "data": data
        })

    def publish_duplicate_without_storing(self, key, data):
        self.send({
            "type": "PUBLISH",
            "key": key,
            "data": data
        })

    def get(self, key):
        self.send({
            "type": "GET",
            "key": key
        })

    def delete(self, key):
        self.send({
            "type": "DELETE",
            "key": key
        })

    def wait_for(self, predicate, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                for message in self.messages:
                    if predicate(message):
                        return message
            time.sleep(0.05)
        return None

    def close(self):
        self.running = False
        try:
            self.socket.close()
        except OSError:
            pass

    def force_disconnect(self):
        self.running = False
        try:
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack("hh", 1, 0)
            )
        except OSError:
            pass

        try:
            self.socket.close()
        except OSError:
            pass


def wait_for_port(host, port, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def start_server(host, port):
    process = subprocess.Popen(
        [sys.executable, "-B", "-u", "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if not wait_for_port(host, port):
        output = ""
        if process.stdout:
            output = process.stdout.read()
        process.terminate()
        raise RuntimeError(f"Serverul nu a pornit pe {host}:{port}.\n{output}")

    return process


def assert_message(message, error):
    if message is None:
        raise AssertionError(error)


def run_demo(host, port):
    server = start_server(host, port)
    client_a = None
    client_b = None

    try:
        print("\n[1] Conectam doi clienti.")
        client_a = DemoClient("CLIENT_A", host, port)
        client_b = DemoClient("CLIENT_B", host, port)

        assert_message(
            client_a.wait_for(lambda message: message.get("type") == "KEY_LIST"),
            "CLIENT_A nu a primit KEY_LIST."
        )
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "KEY_LIST"),
            "CLIENT_B nu a primit KEY_LIST."
        )

        print("\n[2] CLIENT_A publica doua obiecte: obj1 si obj2.")
        for key, value in DEMO_OBJECTS.items():
            client_a.publish(key, value)
            assert_message(
                client_a.wait_for(lambda message, expected_key=key:
                                  message.get("type") == "PUBLISH_OK"
                                  and message.get("key") == expected_key),
                f"CLIENT_A nu a primit PUBLISH_OK pentru {key}."
            )
            assert_message(
                client_b.wait_for(lambda message, expected_key=key:
                                  message.get("type") == "KEY_ADDED"
                                  and message.get("key") == expected_key),
                f"CLIENT_B nu a primit notificarea KEY_ADDED pentru {key}."
            )

        print("\n[3] Verificam erori: cheie inexistenta, duplicat si delete fara drept.")
        client_b.get("nu-exista")
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "ERROR"
                              and "nu exista" in message.get("message", "")),
            "CLIENT_B nu a primit eroare pentru cheie inexistenta."
        )

        client_b.publish_duplicate_without_storing("obj1", {"duplicat": True})
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "ERROR"
                              and "exista deja" in message.get("message", "")),
            "CLIENT_B nu a primit eroare pentru cheie duplicata."
        )

        client_b.delete("obj1")
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "ERROR"
                              and "alt client" in message.get("message", "")),
            "CLIENT_B nu a primit eroare pentru stergere fara drept."
        )

        print("\n[4] CLIENT_B cere obj1.")
        client_b.get("obj1")
        result = client_b.wait_for(
            lambda message: message.get("type") == "GET_RESULT"
            and message.get("key") == "obj1"
        )
        assert_message(result, "CLIENT_B nu a primit GET_RESULT.")

        if result.get("data") != DEMO_OBJECTS["obj1"]:
            raise AssertionError("Obiectul primit de CLIENT_B nu este cel publicat.")

        print("\n[5] CLIENT_B cere obj2, obiect mai mare decat un recv(4096).")
        client_b.get("obj2")
        large_result = client_b.wait_for(
            lambda message: message.get("type") == "GET_RESULT"
            and message.get("key") == "obj2"
        )
        assert_message(large_result, "CLIENT_B nu a primit GET_RESULT pentru obj2.")

        if large_result.get("data") != DEMO_OBJECTS["obj2"]:
            raise AssertionError("Obiectul mare primit de CLIENT_B nu este corect.")

        print("\n[6] CLIENT_A sterge obj1.")
        client_a.delete("obj1")
        assert_message(
            client_a.wait_for(lambda message: message.get("type") == "DELETE_OK"
                              and message.get("key") == "obj1"),
            "CLIENT_A nu a primit DELETE_OK."
        )
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "KEY_REMOVED"
                              and message.get("key") == "obj1"),
            "CLIENT_B nu a primit notificarea KEY_REMOVED."
        )

        print("\n[7] CLIENT_A se deconecteaza fortat. Serverul trebuie sa elimine obj2.")
        client_a.force_disconnect()
        assert_message(
            client_b.wait_for(lambda message: message.get("type") == "KEY_REMOVED"
                              and message.get("key") == "obj2"),
            "CLIENT_B nu a primit KEY_REMOVED pentru obj2 dupa deconectare."
        )

        print("\nDemo cap-coada reusit cu minimum 2 clienti.")
    finally:
        if client_a:
            client_a.close()
        if client_b:
            client_b.close()
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ruleaza un demo cap-coada cu server + 2 clienti."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main():
    args = parse_args()
    run_demo(args.host, args.port)


if __name__ == "__main__":
    main()
