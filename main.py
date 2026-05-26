import math
import logging
import arcade
import pymunk

from game_object import Bird, BlueBird, Column, Pig, YellowBird
from game_logic import get_impulse_vector, Point2D, get_distance

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("arcade").setLevel(logging.WARNING)
logging.getLogger("pymunk").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

logger = logging.getLogger("main")

WIDTH = 1800
HEIGHT = 800
TITLE = "Angry birds"
GRAVITY = -900

# Puntaje minimo para pasar de nivel
SCORE_PER_LEVEL = 500

# Cola de tipos de pajaros disponibles por turno (se repite ciclicamente)
BIRD_QUEUE = ["red", "yellow", "blue", "red", "yellow"]

# Posicion fija del resortera (slingshot) — base de lanzamiento
SLING_X = 400          # coordenada X del centro del resortera
SLING_Y = 20           # coordenada Y de la base inferior del sprite
SLING_SCALE = 1.6      # escala de renderizado del sprite sling-3.png
SLING_FORK_HEIGHT = 160 # distancia vertical desde SLING_Y hasta las puntas de la horquilla

# Zona de interaccion del resortera: rectangulo invisible alrededor de la imagen.
# Solo se inicia el arrastre si el clic cae dentro de esta caja.
SLING_HIT_W = 512   # mitad del ancho de la caja (pixels a cada lado de SLING_X)
SLING_HIT_H = 768   # altura total de la caja desde SLING_Y hacia arriba

# Tamano de los iconos de pajaro en el HUD de cola
QUEUE_ICON_SCALE = 0.04
QUEUE_ICON_SIZE = 30   # tamano visual aproximado en pixeles


class App(arcade.View):
    def __init__(self, level: int = 1, score: int = 0):
        super().__init__()
        self.background = arcade.load_texture("assets/img/background3.png")

        # nivel y puntaje acumulado
        self.level = level
        self.score = score
        self.level_score = 0  # puntaje ganado en este nivel

        # crear espacio de pymunk
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)

        # agregar piso
        floor_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        floor_shape = pymunk.Segment(floor_body, [0, 15], [WIDTH, 15], 0.0)
        floor_shape.friction = 10
        self.space.add(floor_body, floor_shape)

        # Paredes laterales y techo para que los objetos no escapen de la pantalla.
        # Se usan segmentos estaticos en los cuatro bordes.
        wall_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        # Pared izquierda
        left_wall = pymunk.Segment(wall_body, (0, 15), (0, HEIGHT), 0.0)
        left_wall.elasticity = 0.3
        left_wall.friction = 1
        # Pared derecha
        right_wall = pymunk.Segment(wall_body, (WIDTH, 15), (WIDTH, HEIGHT), 0.0)
        right_wall.elasticity = 0.3
        right_wall.friction = 1
        # Techo (evita que cerdos o pajaros salgan por arriba)
        top_wall = pymunk.Segment(wall_body, (0, HEIGHT), (WIDTH, HEIGHT), 0.0)
        top_wall.elasticity = 0.2
        top_wall.friction = 0
        self.space.add(wall_body, left_wall, right_wall, top_wall)

        self.sprites = arcade.SpriteList()
        self.birds = arcade.SpriteList()
        self.world = arcade.SpriteList()
        self.add_columns()
        self.add_pigs()

        # cargar la textura del slingshot
        self.sling_texture = arcade.load_texture("assets/img/sling-3.png")

        # texturas de los iconos de cola (pequeños, solo para el HUD)
        self._bird_textures = {
            "red":    arcade.load_texture("assets/img/red-bird3.png"),
            "yellow": arcade.load_texture("assets/img/yellow.png"),
            "blue":   arcade.load_texture("assets/img/blue.png"),
        }

        self.start_point = Point2D()
        self.end_point = Point2D()
        self.distance = 0
        self.draw_line = False

        # indice en la cola de tipos de pajaro
        self._bird_queue_index = 0

        # agregar un collision handler
        self.handler = self.space.add_default_collision_handler()
        self.handler.post_solve = self.collision_handler

    # ------------------------------------------------------------------
    # Helpers de nivel
    # ------------------------------------------------------------------

    def _current_bird_type(self) -> str:
        """Devuelve el tipo del siguiente pajaro a lanzar."""
        return BIRD_QUEUE[self._bird_queue_index % len(BIRD_QUEUE)]

    def _advance_bird_queue(self):
        """Avanza al siguiente tipo en la cola."""
        self._bird_queue_index += 1

    def _check_level_complete(self):
        """
        Comprueba si todos los cerdos han sido eliminados; si es asi,
        avanza al siguiente nivel.
        """
        pigs_alive = [obj for obj in self.world if isinstance(obj, Pig)]
        if not pigs_alive:
            logger.debug(f"Nivel {self.level} completado con puntaje {self.level_score}")
            self._go_to_next_level()

    def _go_to_next_level(self):
        """Crea una nueva instancia de App con el nivel incrementado."""
        next_view = App(level=self.level + 1, score=self.score + self.level_score)
        self.window.show_view(next_view)

    # ------------------------------------------------------------------
    # Construccion del escenario — generacion procedural por nivel
    # ------------------------------------------------------------------

    def _level_seed(self) -> int:
        """Semilla determinista basada en el nivel (mismo nivel = mismo layout)."""
        return self.level * 31337

    def add_columns(self):
        """
        Genera estructuras de columnas de forma procedural segun el nivel.

        Algoritmo:
          - Nivel 1-2: una sola torre simple de 1-2 columnas apiladas.
          - Nivel 3-4: dos grupos de columnas con separacion variable.
          - Nivel 5+:  tres o mas grupos; algunos grupos forman un arco
                       (una columna encima de dos adyacentes).

        La posicion X de cada grupo se distribuye uniformemente en la
        mitad derecha de la pantalla, con algo de variacion pseudoaleatoria
        derivada del nivel para que cada nivel se vea diferente.
        """
        import random
        rng = random.Random(self._level_seed())

        # Cantidad de grupos aumenta con el nivel (minimo 1, maximo 4)
        num_groups = min(1 + self.level // 2, 4)

        # Zona de colocacion: mitad derecha de la pantalla con margen
        zone_left  = WIDTH // 2 + 80
        zone_right = WIDTH - 120
        zone_width = zone_right - zone_left

        # Distribuir los grupos de forma uniforme con variacion
        for g in range(num_groups):
            base_x = zone_left + int(zone_width * (g + 0.5) / num_groups)
            # Variacion horizontal por nivel para evitar layouts identicos
            jitter = rng.randint(-40, 40)
            gx = base_x + jitter

            # Altura de columna (todas las columnas tienen la misma altura de sprite)
            # Apilar 1 o 2 columnas segun el nivel
            stack = 1 if self.level < 3 else rng.randint(1, 2)
            col_h = 80  # altura aproximada de una columna en pixeles

            for s in range(stack):
                cy = 50 + s * col_h
                column = Column(gx, cy, self.space)
                self.sprites.append(column)
                self.world.append(column)

            # A partir del nivel 3, agregar una columna "techo" formando arco
            if self.level >= 3 and num_groups >= 2 and g < num_groups - 1:
                # Solo cada dos grupos coloca un techo entre ellos
                if rng.random() < 0.6:
                    next_x = zone_left + int(zone_width * (g + 1 + 0.5) / num_groups) + rng.randint(-40, 40)
                    roof_x = (gx + next_x) // 2
                    roof_y = 50 + stack * col_h
                    roof = Column(roof_x, roof_y, self.space)
                    self.sprites.append(roof)
                    self.world.append(roof)

    def add_pigs(self):
        """
        Coloca cerdos de forma procedural segun el nivel.

        Algoritmo:
          - La cantidad de cerdos aumenta con el nivel (1 en nivel 1, hasta 5).
          - Los cerdos se distribuyen entre las estructuras de columnas
            usando la misma semilla que add_columns para coherencia.
          - Algunos cerdos se elevan sobre columnas (nivel > 2).
        """
        import random
        rng = random.Random(self._level_seed() + 1)  # semilla distinta a columnas

        pig_count = min(1 + self.level, 5)

        # Zona de colocacion: mitad derecha con margen interno
        zone_left  = WIDTH // 2 + 60
        zone_right = WIDTH - 80

        for i in range(pig_count):
            # Distribuir cerdos uniformemente con jitter
            t = (i + 0.5) / pig_count
            px = int(zone_left + t * (zone_right - zone_left)) + rng.randint(-30, 30)

            # A partir del nivel 3, algunos cerdos se elevan sobre una columna
            if self.level >= 3 and rng.random() < 0.4:
                py = 100 + 80  # encima de una columna apilada
            else:
                py = 100

            pig = Pig(px, py, self.space)
            self.sprites.append(pig)
            self.world.append(pig)

    # ------------------------------------------------------------------
    # Collision handler
    # ------------------------------------------------------------------

    def collision_handler(self, arbiter, space, data):
        impulse_norm = arbiter.total_impulse.length
        if impulse_norm < 100:
            return True
        logger.debug(impulse_norm)
        if impulse_norm > 1200:
            for obj in list(self.world):
                if obj.shape in arbiter.shapes:
                    # Sumar puntaje segun el tipo de objeto eliminado
                    if isinstance(obj, Pig):
                        self.level_score += 300
                        self.score += 300
                    else:
                        self.level_score += 100
                        self.score += 100
                    obj.remove_from_sprite_lists()
                    self.space.remove(obj.shape, obj.body)

        return True

    # ------------------------------------------------------------------
    # Fabricar pajaro segun el turno actual
    # ------------------------------------------------------------------

    def _launch_bird(self, x: float, y: float):
        """
        Crea y lanza el pajaro correspondiente al turno actual en la
        posicion del resortera con el impulso calculado desde start_point /
        end_point.
        """
        impulse_vector = get_impulse_vector(self.start_point, self.end_point)
        bird_type = self._current_bird_type()

        # El pajaro sale desde el centro de la horquilla, punto medio entre fork_left y fork_right.
        launch_x = SLING_X  # simetrico: (-55 + 55) / 2 = 0
        launch_y = SLING_Y + SLING_FORK_HEIGHT

        if bird_type == "yellow":
            bird = YellowBird(impulse_vector, launch_x, launch_y, self.space)
        elif bird_type == "blue":
            bird = BlueBird(impulse_vector, launch_x, launch_y, self.space)
        else:
            # "red" — pajaro base por defecto
            bird = Bird("assets/img/red-bird3.png", impulse_vector, launch_x, launch_y, self.space)

        self.sprites.append(bird)
        self.birds.append(bird)
        self._advance_bird_queue()
        logger.debug(f"Lanzado pajaro tipo '{bird_type}' desde resortera ({launch_x}, {launch_y})")

    # ------------------------------------------------------------------
    # Eventos de entrada
    # ------------------------------------------------------------------

    def on_update(self, delta_time: float):
        self.space.step(1 / 60.0)  # actualiza la simulacion de las fisicas
        self.sprites.update(delta_time)
        # Verificar si el nivel fue completado en este frame
        self._check_level_complete()

    def on_mouse_press(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            # Primero revisar si hay un pajaro especial en vuelo que
            # debe activar su habilidad al recibir este clic.
            # Se da prioridad a la habilidad sobre el inicio de arrastre
            # cuando ya hay pajaros en vuelo con habilidades disponibles.
            if self._try_activate_bird_ability():
                return  # el clic fue consumido por la habilidad

            # Verificar que el clic cayo dentro de la zona de interaccion
            # del resortera (caja invisible alrededor de la imagen).
            # Esto evita lanzar pajaros por accidente al hacer clic en
            # cualquier parte de la pantalla.
            in_sling_zone = (
                abs(x - SLING_X) <= SLING_HIT_W
                and SLING_Y <= y <= SLING_Y + SLING_HIT_H
            )
            if not in_sling_zone:
                return  # clic fuera del resortera, ignorar

            # Sin habilidad activa: iniciar gesto de arrastre (slingshot)
            self.start_point = Point2D(x, y)
            self.end_point = Point2D(x, y)
            self.draw_line = True
            logger.debug(f"Start Point: {self.start_point}")

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if buttons == arcade.MOUSE_BUTTON_LEFT:
            self.end_point = Point2D(x, y)
            logger.debug(f"Dragging to: {self.end_point}")

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            if not self.draw_line:
                return  # el press fue consumido por una habilidad, ignorar
            logger.debug(f"Releasing from: {self.end_point}")
            self.draw_line = False
            self._launch_bird(x, y)

    # ------------------------------------------------------------------
    # Ruteo de habilidades especiales
    # ------------------------------------------------------------------

    def _try_activate_bird_ability(self) -> bool:
        """
        Recorre los pajaros en vuelo y activa la habilidad del primero
        que aun no la haya usado. Devuelve True si alguna habilidad fue
        activada (el clic fue consumido).
        """
        for bird in list(self.birds):
            if isinstance(bird, YellowBird) and not bird._boost_used:
                bird.activate_boost()
                logger.debug("YellowBird: boost activado")
                return True
            if isinstance(bird, BlueBird) and not bird._split_used:
                bird.activate_split(self.sprites, self.birds)
                logger.debug("BlueBird: division activada")
                return True
        return False

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------

    def _draw_slingshot(self):
        """
        Dibuja el resortera: sprite de la base y la banda elastica cuando
        el usuario esta arrastrando.
        """
        arcade.draw_texture_rect(  # sprite del resortera
            self.sling_texture,
            arcade.LRBT(
                SLING_X - self.sling_texture.width  * SLING_SCALE / 2,
                SLING_X + self.sling_texture.width  * SLING_SCALE / 2,
                SLING_Y,
                SLING_Y + self.sling_texture.height * SLING_SCALE,
            ),
        )

        # Coordenadas de las dos puntas de la horquilla, alineadas con el sprite
        # de sling-3.png. Las puntas estan simetricas respecto al centro de la imagen.
        fork_left  = (SLING_X - 55, SLING_Y + SLING_FORK_HEIGHT)
        fork_right = (SLING_X + 55, SLING_Y + SLING_FORK_HEIGHT)

        if self.draw_line:
            arcade.draw_line(
                fork_left[0], fork_left[1],
                self.end_point.x, self.end_point.y,
                arcade.color.DARK_BROWN, 3,
            )
            arcade.draw_line(
                fork_right[0], fork_right[1],
                self.end_point.x, self.end_point.y,
                arcade.color.DARK_BROWN, 3,
            )
        else:
            arcade.draw_line(
                fork_left[0], fork_left[1],
                fork_right[0], fork_right[1],
                arcade.color.DARK_BROWN, 3,
            )

    def _draw_bird_queue(self):
        """
        Dibuja una fila compacta de iconos de pajaros proximos a lanzar.
        Solo se muestran 4 pajaros (el actual + 3 siguientes) para evitar
        saturar la pantalla. El pajaro actual va con un borde dorado sutil.
        Texto en negro para mejor legibilidad sobre el fondo de juego.
        """
        visible   = 4       # turno actual + 3 siguientes
        icon_size = 22      # tamano base del icono en pixeles (mas pequeno)
        padding   = 6       # espacio entre iconos
        start_x   = 50
        start_y   = 52

        # Fondo semitransparente para la cola (panel compacto)
        panel_w = visible * (icon_size + padding) + 10
        arcade.draw_rect_filled(
            arcade.XYWH(start_x + panel_w // 2 - 8, start_y, panel_w, icon_size + 14),
            (0, 0, 0, 90),
        )

        for i in range(visible):
            idx = (self._bird_queue_index + i) % len(BIRD_QUEUE)
            bird_type = BIRD_QUEUE[idx]
            texture = self._bird_textures.get(bird_type)
            if texture is None:
                continue

            cx = start_x + i * (icon_size + padding)
            cy = start_y

            if i == 0:
                # Pajaro actual: ligeramente mas grande, borde dorado
                size = icon_size * 1.25
                arcade.draw_circle_outline(cx, cy, size / 2 + 3, (200, 170, 0), 2)
            else:
                size = icon_size * 0.8

            arcade.draw_texture_rect(
                texture,
                arcade.LRBT(cx - size / 2, cx + size / 2, cy - size / 2, cy + size / 2),
            )

        # Etiqueta de la cola en negro
        arcade.draw_text(
            "Next:",
            x=start_x - 40, y=start_y - 7,
            color=arcade.color.BLACK,
            font_size=11,
            bold=True,
        )

    def on_draw(self):
        self.clear()
        # arcade.draw_lrwh_rectangle_textured(0, 0, WIDTH, HEIGHT, self.background)
        arcade.draw_texture_rect(self.background, arcade.LRBT(0, WIDTH, 0, HEIGHT))
        self.sprites.draw()

        # Dibujar el resortera (slingshot) con banda elastica si se esta apuntando
        self._draw_slingshot()

        if self.draw_line:
            arcade.draw_line(self.start_point.x, self.start_point.y, self.end_point.x, self.end_point.y,
                             arcade.color.BLACK, 3)

        # Cola de pajaros proximos
        self._draw_bird_queue()

        # --- HUD: nivel, puntaje y tipo del siguiente pajaro (texto negro) ---
        arcade.draw_text(
            f"Nivel: {self.level}",
            x=20, y=HEIGHT - 40,
            color=arcade.color.BLACK,
            font_size=22,
            bold=True,
        )
        arcade.draw_text(
            f"Puntaje: {self.score}",
            x=20, y=HEIGHT - 70,
            color=arcade.color.BLACK,
            font_size=18,
            bold=True,
        )
        next_bird_label = {
            "red":    "Rojo",
            "yellow": "Amarillo [boost]",
            "blue":   "Azul [x3]",
        }.get(self._current_bird_type(), self._current_bird_type())
        arcade.draw_text(
            f"Sig: {next_bird_label}",
            x=20, y=HEIGHT - 96,
            color=arcade.color.BLACK,
            font_size=15,
        )


def main():
    window = arcade.Window(WIDTH, HEIGHT, TITLE)
    game = App()
    window.show_view(game)
    arcade.run()


if __name__ == "__main__":
    main()