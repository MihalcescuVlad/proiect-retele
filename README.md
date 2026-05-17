# Proiect Retele - Partajarea de obiecte in memorie

Aplicatia implementeaza un sistem client-server pentru partajarea de obiecte JSON tinute in memoria clientilor.

Serverul actioneaza ca registru si intermediar:

- mentine un dictionar `cheie -> client detinator`;
- trimite lista de chei la conectarea clientilor;
- verifica unicitatea cheilor publicate;
- cere obiectul de la clientul detinator si il livreaza clientului solicitant;
- sterge cheile publicate manual sau automat la deconectarea clientului;
- trimite notificari live pentru chei adaugate si sterse.

Serverul nu persista obiectele. Continutul obiectelor ramane in memoria clientilor.

## Fisiere principale

- `server.py` - server TCP concurent, registru de chei si intermediar pentru transfer.
- `client.py` - CLI interactiv pentru publicare, listare, cerere si stergere obiecte.
- `client_test.py` - client simplu de test existent.
- `demo_e2e.py` - demo automat cap-coada cu server si minimum 2 clienti.
- `Dockerfile` - rulare server in container Docker.
- `PROTOCOL.md` - protocolul complet de mesaje.
- `VIDEO_SCENARIO.md` - scenariu pentru demo video.

## Cerinte

- Python 3.10+.
- Nu sunt necesare librarii externe.
- Port implicit: `5000`.

## Rulare server in Docker

Build imagine:

```bash
docker build -t proiect-retele-server .
```

Pornire server:

```bash
docker run --rm -p 5000:5000 proiect-retele-server
```

## Rulare client

Porneste cate un client in terminale separate:

```bash
python client.py
```

Pentru alt host sau port:

```bash
python client.py --host 127.0.0.1 --port 5000
```

Pentru testarea transferului intre clienti, foloseste cel putin doi clienti conectati la acelasi server.

## Comenzi CLI

Comenzile principale pentru demo sunt:

```text
list
publish obj1 {"nume":"test","valoare":123}
get obj1
delete obj1
exit
```

Comenzi suplimentare utile:

```text
help
demos
publish-demo sensor obj2
local
show obj1
force-disconnect
```

`list` afiseaza cheile curente cunoscute de client. Lista este actualizata automat prin notificarile live `KEY_ADDED` si `KEY_REMOVED`.

## Demo manual pentru video

Terminal 1 - server in Docker:

```bash
docker build -t proiect-retele-server .
docker run --rm -p 5000:5000 proiect-retele-server
```

Terminal 2 - Client A:

```bash
python client.py
```

In Client A, publica doua obiecte cu chei diferite:

```text
list
publish obj1 {"nume":"test","valoare":123}
publish obj2 {"tip":"demo","activ":true}
local
```

Terminal 3 - Client B:

```bash
python client.py
```

In Client B:

```text
list
get obj1
```

Client B primeste obiectul publicat de Client A. Pe Client A se vede notificarea ca serverul a cerut obiectul si ca obiectul a fost trimis inapoi catre server.

Stergere din Client A:

```text
delete obj1
```

Client B primeste notificarea live `KEY_REMOVED` pentru `obj1`.

Deconectare fortata din Client A:

```text
force-disconnect
```

Client B primeste notificarea `KEY_REMOVED` pentru `obj2`, deoarece serverul curata automat cheile detinute de clientul deconectat.

## Demo automat cap-coada

Scriptul `demo_e2e.py` porneste serverul, conecteaza doi clienti TCP, publica doua obiecte, transfera obiectele, sterge o cheie si verifica stergerea automata la deconectare.

Unul dintre obiecte are payload mare, peste 4096 bytes, pentru a verifica faptul ca protocolul functioneaza si cand mesajele sunt fragmentate in mai multe citiri din socket.

```bash
python demo_e2e.py
```

Rezultat asteptat:

```text
Demo cap-coada reusit cu minimum 2 clienti.
```

## Protocol pe scurt

Comunicarea este TCP. Fiecare mesaj este JSON si se termina cu newline (`\n`). Implementarea citeste mesajele intr-un buffer, deci suporta mesaje fragmentate si obiecte mai mari decat un singur `recv(4096)`.

### Client -> Server

Publicare cheie:

```json
{ "type": "PUBLISH", "key": "obj1", "data": { "nume": "test", "valoare": 123 } }
```

Cerere obiect:

```json
{ "type": "GET", "key": "obj1" }
```

Stergere cheie:

```json
{ "type": "DELETE", "key": "obj1" }
```

Raspuns cu obiectul cerut de server:

```json
{ "type": "OBJECT_DATA", "request_id": "uuid", "key": "obj1", "data": { "nume": "test" } }
```

### Server -> Client

Lista initiala de chei:

```json
{ "type": "KEY_LIST", "keys": ["obj1"] }
```

Notificari live:

```json
{ "type": "KEY_ADDED", "key": "obj1" }
{ "type": "KEY_REMOVED", "key": "obj1" }
```

Serverul cere obiectul de la detinator:

```json
{ "type": "SEND_OBJECT", "request_id": "uuid", "key": "obj1" }
```

Rezultatul pentru clientul care a cerut cheia:

```json
{ "type": "GET_RESULT", "key": "obj1", "data": { "nume": "test", "valoare": 123 } }
```

Confirmari si erori:

```json
{ "type": "PUBLISH_OK", "key": "obj1" }
{ "type": "DELETE_OK", "key": "obj1" }
{ "type": "ERROR", "message": "Cheia 'obj1' exista deja." }
```

Protocolul complet este documentat in `PROTOCOL.md`.

## Testare

Verificare sintaxa:

```bash
python -m py_compile server.py client.py client_test.py demo_e2e.py
```

Test cap-coada cu minimum 2 clienti:

```bash
python demo_e2e.py
```
