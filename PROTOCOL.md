# Protocol de comunicare client-server

Aplicatia foloseste TCP. Mesajele sunt obiecte JSON serializate text, delimitate prin newline (`\n`).

Atat serverul, cat si clientul citesc din socket intr-un buffer si proceseaza cate un mesaj complet atunci cand apare newline. Astfel, mesajele pot fi mai mari decat un singur `recv(4096)` si pot fi primite fragmentat.

Serverul functioneaza ca registru de chei si intermediar pentru transferul obiectelor. El pastreaza doar:

```text
cheie -> client detinator
```

Continutul obiectului ramane in memoria clientului detinator.

## 1. Conectare client

La conectarea unui client, serverul trimite lista curenta de chei publicate.

Server -> Client:

```json
{
  "type": "KEY_LIST",
  "keys": ["obj1", "obj2"]
}
```

## 2. Publicarea unui obiect

Clientul trimite cheia si continutul obiectului. Obiectul trebuie sa fie serializabil JSON.

Client -> Server:

```json
{
  "type": "PUBLISH",
  "key": "obj1",
  "data": {
    "nume": "test",
    "valoare": 123
  }
}
```

Daca cheia este unica, serverul retine asocierea `obj1 -> client` si confirma publicarea.

Server -> Client:

```json
{
  "type": "PUBLISH_OK",
  "key": "obj1"
}
```

Apoi serverul notifica toti clientii conectati.

Server -> Clienti:

```json
{
  "type": "KEY_ADDED",
  "key": "obj1"
}
```

Daca cheia exista deja:

```json
{
  "type": "ERROR",
  "message": "Cheia 'obj1' exista deja."
}
```

## 3. Regasirea unui obiect dupa cheie

Clientul solicitant cere obiectul dupa cheia publicata.

Client -> Server:

```json
{
  "type": "GET",
  "key": "obj1"
}
```

Serverul verifica daca cheia exista. Daca exista, trimite o cerere catre clientul detinator.

Server -> Detinator:

```json
{
  "type": "SEND_OBJECT",
  "key": "obj1",
  "request_id": "uuid-generat-de-server"
}
```

Clientul detinator trimite obiectul inapoi catre server.

Detinator -> Server:

```json
{
  "type": "OBJECT_DATA",
  "request_id": "uuid-generat-de-server",
  "key": "obj1",
  "data": {
    "nume": "test",
    "valoare": 123
  }
}
```

Serverul trimite obiectul catre clientul care l-a cerut.

Server -> Solicitant:

```json
{
  "type": "GET_RESULT",
  "key": "obj1",
  "data": {
    "nume": "test",
    "valoare": 123
  }
}
```

Daca cheia nu exista:

```json
{
  "type": "ERROR",
  "message": "Cheia 'obj1' nu exista."
}
```

## 4. Stergerea unei chei

Doar clientul care a publicat cheia o poate sterge.

Client -> Server:

```json
{
  "type": "DELETE",
  "key": "obj1"
}
```

Daca solicitantul este detinatorul, serverul sterge cheia.

Server -> Client:

```json
{
  "type": "DELETE_OK",
  "key": "obj1"
}
```

Serverul notifica toti clientii conectati.

Server -> Clienti:

```json
{
  "type": "KEY_REMOVED",
  "key": "obj1"
}
```

Daca un alt client incearca sa stearga cheia:

```json
{
  "type": "ERROR",
  "message": "Nu poti sterge o cheie publicata de alt client."
}
```

## 5. Deconectare client

Cand un client se deconecteaza, serverul elimina automat toate cheile publicate de acel client.

Pentru fiecare cheie eliminata, serverul trimite:

```json
{
  "type": "KEY_REMOVED",
  "key": "obj1"
}
```

## 6. Format obiecte

Obiectele sunt transmise ca valori JSON in campul `data`. Exemple valide:

```json
{
  "nume": "test",
  "valoare": 123
}
```

```json
{
  "nume": "obiect-mare",
  "payload": "text lung ..."
}
```

Pentru date binare, continutul trebuie convertit intr-o forma JSON, de exemplu Base64.
