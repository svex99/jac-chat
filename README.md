# jac-chat
Chat using zmq sockets with an architecture client-server, but this time the server implement a multithread philosophy and the pattern dispatcher-worker.

## Implementación

La implementación de `jac-chat` parte del chat de grupo `0mq-chat` (cliente-servidor) implementado sobre sockets ZMQ en una tarea anterior. `jac-chat` mantiene las funcionalidades de este:

- La comunicación entre cada cliente y el servidor se asíncrona.
- Cada mensaje que llega de un cliente al servidor es enviado a los demás clientes.
- Los clientes son notificados cuando otro entra/sale del chat. 
- Los clientes son notificados cuando el servidor se cierra (`ctrl+C`).
- Si el servidor se reinicia los clientes siguen mateniendo la conexión.
  
Pero a diferencia del servidor de `0mq-chat`, el cual desde un mismo hilo, recibía un request, la enviaba a todos los clientes, y una vez que esto se completaba era que podía procesar el siguiente request, `jac-chat` sigue el patrón **Dispacther-Worker** con una filosofía multihilo en el servidor. Un hilo (Dispatcher) recibe los request, los coloca en una cola y otro hilo que este libre, de un conjunto de hilos (Workers), procesa el request enviándolo a todos los clientes que sea necesario. De esta forma el server procesa los requests de forma paralela en cada uno de los workers y ofrece un mejor tiempo de respuesta ante la latencia de la red.