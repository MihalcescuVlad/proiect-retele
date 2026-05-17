# Scenariu video demo

Durata recomandata: 4-6 minute.

## 1. Introducere

Spune pe scurt:

```text
Aplicatia este un sistem client-server pentru partajarea obiectelor JSON tinute in memoria clientilor.
Serverul nu stocheaza obiectele, ci pastreaza doar asocierea cheie -> client detinator.
Cand un client cere un obiect, serverul il cere de la detinator si il livreaza solicitantului.
```

Arata fisierele:

```text
server.py
client.py
demo_e2e.py
Dockerfile
README.md
PROTOCOL.md
```

## 2. Pornire server in Docker

Terminal 1:

```bash
docker build -t proiect-retele-server .
docker run --rm -p 5000:5000 proiect-retele-server
```

Explica:

```text
Serverul ruleaza in Docker, asculta pe portul 5000 si accepta mai multi clienti in paralel.
```

## 3. Pornire Client A

Terminal 2:

```bash
python client.py
```

In Client A:

```text
list
publish obj1 {"nume":"test","valoare":123}
publish obj2 {"tip":"demo","activ":true}
local
```

Explica:

```text
Clientul A publica doua obiecte cu chei diferite.
Obiectele raman in memoria Clientului A.
Serverul retine doar obj1 -> Client A si obj2 -> Client A.
```

## 4. Pornire Client B si notificari live

Terminal 3:

```bash
python client.py
```

In Client B:

```text
list
```

Explica:

```text
Clientul B primeste lista curenta de chei la conectare.
Daca este conectat deja cand Clientul A publica, vede notificari live KEY_ADDED pentru obj1 si obj2.
```

## 5. Regasire obiect prin server

In Client B:

```text
get obj1
```

Explica fluxul:

```text
Clientul B cere cheia obj1.
Serverul vede ca obj1 este detinuta de Clientul A.
Serverul trimite SEND_OBJECT catre Clientul A.
Clientul A raspunde cu OBJECT_DATA.
Serverul trimite GET_RESULT catre Clientul B.
```

## 6. Stergere si notificare live

In Client A:

```text
delete obj1
```

In Client B:

```text
list
```

Explica:

```text
Cheia obj1 este stearsa din server, iar clientii primesc notificarea KEY_REMOVED.
Cheia obj2 ramane publicata, pentru ca nu a fost stearsa.
```

## 7. Deconectare fortata si curatare automata

In Client A:

```text
force-disconnect
```

In Client B:

```text
list
```

Explica:

```text
Clientul A se inchide brusc.
Serverul detecteaza deconectarea si sterge automat toate cheile ramase ale Clientului A.
Clientul B primeste KEY_REMOVED pentru obj2.
```

## 8. Demo automat cap-coada

Terminal separat, fara server pornit deja pe portul 5000:

```bash
python demo_e2e.py
```

Explica:

```text
Scriptul porneste serverul, conecteaza doi clienti, publica doua obiecte, transfera obiectele, sterge obj1 si verifica eliminarea automata a obj2 dupa deconectarea fortata.
Al doilea obiect are payload mare, pentru a testa mesajele fragmentate pe socket.
```

Rezultat asteptat:

```text
Demo cap-coada reusit cu minimum 2 clienti.
```

## 9. Incheiere

Concluzie:

```text
Am demonstrat serverul in Docker, doi clienti, publicarea a doua obiecte, notificari live, transfer prin server, stergere de catre detinator si curatare automata la deconectare fortata.
```
