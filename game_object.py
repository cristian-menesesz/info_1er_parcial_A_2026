import math
import arcade
import pymunk
from game_logic import ImpulseVector

# Escala visual para los pajaros especiales; ajustar si los sprites
# tienen dimensiones diferentes al pajaro rojo base (radius ~12 px).
# El pajaro rojo usa scale=1 porque red-bird3.png ya es pequeno (~24px).
# yellow.png y blue.png son imagenes grandes, por eso necesitan escala
# reducida — igual que pig_failed.png que usa 0.1 en Pig.__init__.
BIRD_SCALE = 0.06   # escala conservadora para yellow y blue


class Bird(arcade.Sprite):
    """
    Bird class. This represents an angry bird. All the physics is handled by Pymunk,
    the init method only set some initial properties
    """
    def __init__(
        self,
        image_path: str,
        impulse_vector: ImpulseVector,
        x: float,
        y: float,
        space: pymunk.Space,
        mass: float = 5,
        radius: float = 12,
        max_impulse: float = 50000,
        power_multiplier: float = 10,
        elasticity: float = 0.8,
        friction: float = 1,
        collision_layer: int = 0,
        scale: float = 1,
    ):
        # Pasar la escala directamente al constructor del sprite,
        # igual que Pig hace con 0.1 para su imagen grande.
        super().__init__(image_path, scale)
        # body
        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)
        body.position = (x, y)

        impulse = min(max_impulse, impulse_vector.impulse) * power_multiplier
        impulse_pymunk = impulse * pymunk.Vec2d(1, 0)
        # apply impulse
        body.apply_impulse_at_local_point(impulse_pymunk.rotated(impulse_vector.angle))
        # shape
        shape = pymunk.Circle(body, radius)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.collision_type = collision_layer

        space.add(body, shape)

        self.body = body
        self.shape = shape

    def update(self, delta_time):
        """
        Update the position of the bird sprite based on the physics body position
        """
        self.center_x = self.shape.body.position.x
        self.center_y = self.shape.body.position.y
        self.radians = self.shape.body.angle


class Pig(arcade.Sprite):
    def __init__(
        self,
        x: float,
        y: float,
        space: pymunk.Space,
        mass: float = 2,
        elasticity: float = 0.8,
        friction: float = 0.4,
        collision_layer: int = 0,
    ):
        super().__init__("assets/img/pig_failed.png", 0.1)
        moment = pymunk.moment_for_circle(mass, 0, self.width / 2 - 3)
        body = pymunk.Body(mass, moment)
        body.position = (x, y)
        shape = pymunk.Circle(body, self.width / 2 - 3)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.collision_type = collision_layer
        space.add(body, shape)
        self.body = body
        self.shape = shape

    def update(self, delta_time):
        self.center_x = self.shape.body.position.x
        self.center_y = self.shape.body.position.y
        self.radians = self.shape.body.angle


class PassiveObject(arcade.Sprite):
    """
    Passive object that can interact with other objects.
    """
    def __init__(
        self,
        image_path: str,
        x: float,
        y: float,
        space: pymunk.Space,
        mass: float = 2,
        elasticity: float = 0.8,
        friction: float = 1,
        collision_layer: int = 0,
    ):
        super().__init__(image_path, 1)

        moment = pymunk.moment_for_box(mass, (self.width, self.height))
        body = pymunk.Body(mass, moment)
        body.position = (x, y)
        shape = pymunk.Poly.create_box(body, (self.width, self.height))
        shape.elasticity = elasticity
        shape.friction = friction
        shape.collision_type = collision_layer
        space.add(body, shape)
        self.body = body
        self.shape = shape

    def update(self, delta_time):
        self.center_x = self.shape.body.position.x
        self.center_y = self.shape.body.position.y
        self.radians = self.shape.body.angle


class Column(PassiveObject):
    def __init__(self, x, y, space):
        super().__init__("assets/img/column.png", x, y, space)


class YellowBird(Bird):
    """
    Variante del Bird que, mientras esta en vuelo, puede recibir un "boost".

    Comportamiento esperado:
    - Si el usuario hace clic izquierdo mientras este pajaro esta en vuelo,
      su impulso se multiplica por `power_multiplier` (default 2) aplicado
      en la direccion ACTUAL de movimiento.
    - El boost solo deberia aplicarse una vez (no acumular en cada clic).
    - Recomendacion: usar "assets/img/yellow.png" como sprite.

    Pista: para aplicar el boost, usar
        self.body.apply_impulse_at_local_point(...)
    con un vector en la direccion actual de la velocidad del cuerpo
    (self.body.velocity).
    """

    ### ---------------------- ###
    ### SU IMPLEMENTACION AQUI ###
    ### ---------------------- ###
    def __init__(
        self,
        impulse_vector: ImpulseVector,
        x: float,
        y: float,
        space: pymunk.Space,
        power_multiplier: float = 2,
        **kwargs,
    ):
        # Usar el sprite amarillo recomendado con escala correcta para
        # que coincida visualmente con el pajaro rojo base (~24 px de diametro).
        # Se pasa scale=BIRD_SCALE al constructor, igual que Pig usa 0.1.
        super().__init__("assets/img/yellow.png", impulse_vector, x, y, space, scale=BIRD_SCALE, **kwargs)
        # Multiplicador de boost para el clic en vuelo
        self._power_multiplier = power_multiplier
        # Bandera: el boost solo puede aplicarse una vez
        self._boost_used = False

    def activate_boost(self):
        """
        Aplica el boost en la direccion ACTUAL de movimiento.
        Solo tiene efecto la primera vez que se llama.
        """
        if self._boost_used:
            return  # ya se uso el boost, ignorar clics subsiguientes
        self._boost_used = True

        velocity = self.body.velocity
        speed = velocity.length
        if speed == 0:
            return  # el pajaro no se mueve, no hay direccion definida

        # Vector unitario en la direccion actual de vuelo
        direction = velocity.normalized()
        # Aplicar impulso adicional en esa direccion (masa * velocidad * (mult - 1))
        boost = direction * self.body.mass * speed * (self._power_multiplier - 1)
        self.body.apply_impulse_at_local_point(boost)


class BlueBird(Bird):
    """
    Variante del Bird que se divide en 3 al hacer clic en vuelo.

    Comportamiento esperado:
    - Si el usuario hace clic izquierdo mientras este pajaro esta en vuelo,
      instantaneamente se reemplaza por 3 BlueBirds con direcciones de
      vuelo separadas por +30, 0 y -30 grados respecto a la direccion
      actual. La magnitud de la velocidad se preserva.
    - La division solo deberia ocurrir una vez por pajaro.
    - Recomendacion: usar "assets/img/blue.png" como sprite.

    Pista: para crear los 2 nuevos pajaros se necesita acceso al
    pymunk.Space y a las SpriteLists del juego. El metodo puede devolver
    los nuevos pajaros para que main.py los agregue, o recibir las listas
    como argumento. Esa decision de diseno es parte del ejercicio.
    """

    ### ---------------------- ###
    ### SU IMPLEMENTACION AQUI ###
    ### ---------------------- ###

    # Angulos de separacion en grados para cada uno de los 3 fragmentos
    SPLIT_ANGLES_DEG = [30, 0, -30]

    def __init__(
        self,
        impulse_vector: ImpulseVector,
        x: float,
        y: float,
        space: pymunk.Space,
        _born_from_split: bool = False,
        **kwargs,
    ):
        # Usar el sprite azul recomendado con escala correcta.
        # Se pasa scale=BIRD_SCALE al constructor, igual que Pig usa 0.1.
        super().__init__("assets/img/blue.png", impulse_vector, x, y, space, scale=0.14, **kwargs)
        # Bandera: la division solo puede ocurrir una vez por pajaro
        self._split_used = _born_from_split  # los fragmentos ya no pueden dividirse
        # Guardar referencia al space para usarla al dividirse
        self._space = space

    def activate_split(self, sprites: arcade.SpriteList, birds: arcade.SpriteList):
        """
        Reemplaza este pajaro por 3 BlueBirds con angulos +30, 0 y -30 grados
        respecto a la velocidad actual. Devuelve la lista de nuevos pajaros
        creados para que main.py pueda agregarlos si lo desea.

        Los pajaros nacidos de la division tienen _born_from_split=True,
        lo que les impide volver a dividirse (evita division infinita).

        Args:
            sprites: SpriteList general del juego (para agregar los fragmentos).
            birds:   SpriteList de pajaros activos (para agregar los fragmentos).

        Returns:
            list[BlueBird]: los 3 nuevos pajaros.
        """
        if self._split_used:
            return []  # ya se dividio, ignorar clics subsiguientes
        self._split_used = True

        velocity = self.body.velocity
        speed = velocity.length
        if speed == 0:
            return []  # sin velocidad no hay direccion definida, abortar

        # Angulo actual de vuelo en radianes
        current_angle_rad = math.atan2(velocity.y, velocity.x)

        new_birds = []
        for deg_offset in self.SPLIT_ANGLES_DEG:
            rad_offset = math.radians(deg_offset)
            new_angle = current_angle_rad + rad_offset

            # Convertir velocidad actual a ImpulseVector equivalente.
            # Bird.__init__ calcula: impulse = min(max_impulse, iv.impulse) * power_multiplier
            # Con max_impulse=100, power_multiplier=10 -> max fuerza = 1000.
            # Queremos que la fuerza resultante == mass * speed, entonces:
            #   iv.impulse = (mass * speed) / power_multiplier
            # y nos aseguramos de no exceder max_impulse.
            raw_impulse = (self.body.mass * speed) / 10.0
            iv = ImpulseVector(angle=new_angle, impulse=raw_impulse)

            # Crear el nuevo pajaro en la posicion actual de este pajaro;
            # _born_from_split=True evita que estos fragmentos se dividan de nuevo
            pos = self.body.position
            nb = BlueBird(iv, pos.x, pos.y, self._space, _born_from_split=True)
            new_birds.append(nb)
            sprites.append(nb)
            birds.append(nb)

        # Eliminar este pajaro de todas las listas y del espacio fisico
        self.remove_from_sprite_lists()
        self._space.remove(self.shape, self.body)

        return new_birds