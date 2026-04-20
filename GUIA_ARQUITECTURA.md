# Guia Clara Del Proyecto

## Objetivo

Esta guia sirve como mapa rapido para no perdernos al agregar funciones nuevas.
La idea es separar el proyecto por responsabilidad y decidir primero donde vive
cada cambio antes de editar codigo.

## Regla Principal

Antes de implementar algo, responder estas 4 preguntas:

1. Se ve en pantalla?
2. Cambia reglas del proceso?
3. Manda comandos a la maquina?
4. Solo interpreta, transforma o guarda datos?

La respuesta normalmente nos dice en que capa debe vivir el cambio.

## Modo Claro De Trabajo

### `UI`

Aqui vive lo que el usuario ve o toca.

- Paneles
- Dialogos
- Botones
- Labels
- Combos
- Entradas de texto

Carpetas principales:

- `app/ui/panels`
- `app/ui/dialogs`
- `app/ui/widgets`

La UI no deberia contener reglas importantes de negocio ni logica de protocolo.
Su trabajo principal es mostrar datos y disparar acciones.

### `Controller`

Aqui vive la coordinacion del flujo.

- Decide que accion ejecutar
- Valida el contexto de uso
- Habla con servicios
- Habla con el backend de maquina
- Actualiza el estado visible en UI

Archivos clave:

- `app/controllers/control_controller.py`
- `app/main.py`

Nota actual del repo:

`app/main.py` todavia concentra bastante orquestacion. Cuando agreguemos cosas
nuevas, conviene preferir mover logica a controladores o servicios en lugar de
seguir cargando `main.py`.

### `Service`

Aqui vive la logica reutilizable que no depende directamente de widgets.

- Interpretacion de mensajes
- Reglas de recetas
- Calculos de posicion
- Construccion de comandos
- Configuracion
- Logging

Carpetas y archivos clave:

- `app/services/status_service.py`
- `app/services/recipe_service.py`
- `app/services/config_service.py`
- `app/services/log_service.py`

Si una regla puede probarse sin abrir la UI, probablemente pertenece a un
service.

### `Machine Backend`

Aqui vive la comunicacion con la maquina real o simulada.

- Backend serial real
- Backend simulado
- Adaptacion del estado de maquina
- Comandos de movimiento

Carpeta principal:

- `app/controllers/machine`

Archivos clave:

- `machine_interface.py`
- `serial_machine_controller.py`
- `simulated_machine_controller.py`
- `machine_factory.py`

Esta capa deberia representar "que puede hacer la maquina", no "como se dibuja
en pantalla".

### `State`

Aqui vive el estado compartido simple de la app.

- Conexion
- Receta seleccionada
- Modo manual
- Estado de jog

Archivo clave:

- `app/state/app_state.py`

El state no deberia convertirse en un lugar de logica pesada. Debe guardar
datos simples del momento.

## Como Decidir Donde Va Un Cambio

### Si el cambio agrega un boton, campo o panel nuevo

Empieza en `UI`.

Despues conecta el evento con un controller.

### Si el cambio modifica el flujo de una accion

Empieza en `Controller`.

Ejemplo:

- cuando permitir modo manual
- cuando bloquear un comando
- que hacer al iniciar o detener

### Si el cambio agrega reglas, calculos o transformaciones

Empieza en `Service`.

Ejemplo:

- parsear un mensaje nuevo
- validar una receta
- calcular una posicion
- armar un comando

### Si el cambio implica hablar con la maquina

Empieza en `Machine Backend`.

Ejemplo:

- nuevo comando serial
- nuevo comportamiento del simulador
- nuevo snapshot de estado

### Si el cambio solo guarda una bandera o valor compartido

Empieza en `State`.

## Flujo Recomendado Para Agregar Algo

Cuando queramos meter una funcion nueva, usar este orden:

1. Describir la funcion en una frase.
2. Decidir en que capa vive la responsabilidad principal.
3. Identificar que archivos participan.
4. Hacer el cambio minimo necesario.
5. Probar el flujo completo.

## Regla Practica Para Este Repo

Podemos usar esta guia corta:

- `app/main.py`: orquestacion general, no meter mas logica de la necesaria
- `app/ui/*`: mostrar y capturar interaccion
- `app/controllers/*`: coordinar acciones
- `app/services/*`: reglas reutilizables y transformaciones
- `app/controllers/machine/*`: maquina real o simulada
- `app/state/*`: estado simple compartido

## Cuando Tengamos Duda

Si una funcion toca varias capas, usar esta prioridad:

1. Poner reglas en `services`
2. Poner flujo en `controllers`
3. Dejar la UI lo mas delgada posible
4. Dejar `main.py` como integrador, no como deposito de logica

## Primeras Mejoras Detectadas

Solo como referencia para el futuro:

- `app/main.py` esta muy cargado y conviene seguir sacando logica de ahi
- la interfaz `machine_interface.py` y el backend serial no estan 100% alineados
- ya existe una buena base de separacion, asi que vale la pena reforzarla en vez
  de romperla

## Uso Recomendado Entre Nosotros

Cuando me pidas un cambio, podemos plantearlo asi:

- que quieres lograr
- que comportamiento esperas
- en que pantalla o flujo pasa

Y yo me encargo de ubicarlo en la capa correcta antes de implementarlo.
