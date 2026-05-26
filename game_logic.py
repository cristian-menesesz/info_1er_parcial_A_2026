import math
from dataclasses import dataclass
from logging import getLogger

logger = getLogger(__name__)


@dataclass
class ImpulseVector:
    angle: float
    impulse: float


@dataclass
class Point2D:
    x: float = 0
    y: float = 0


def get_angle_radians(point_a: Point2D, point_b: Point2D) -> float:
    """
    Devuelve el angulo, en radianes, del vector que va de `point_a` a
    `point_b`, medido desde el eje +x.

    Pista: usar math.atan2 sobre las diferencias dy, dx.
    """
    ### ---------------------- ###
    ### SU IMPLEMENTACION AQUI ###
    ### ---------------------- ###
    dx = point_b.x - point_a.x
    dy = point_b.y - point_a.y
    return math.atan2(dy, dx)


def get_distance(point_a: Point2D, point_b: Point2D) -> float:
    """
    Devuelve la distancia euclidiana en pixeles entre `point_a` y `point_b`.
    """
    ### ---------------------- ###
    ### SU IMPLEMENTACION AQUI ###
    ### ---------------------- ###
    dx = point_b.x - point_a.x
    dy = point_b.y - point_a.y
    return math.sqrt(dx * dx + dy * dy)


def get_impulse_vector(start_point: Point2D, end_point: Point2D) -> ImpulseVector:
    """
    Calcula el ImpulseVector que se aplicara al pajaro segun el gesto de
    arrastre del usuario.

    Convencion del resortera (slingshot):
      start_point = posicion donde el usuario hace clic (punto de "anclaje")
      end_point   = posicion donde el usuario suelta el mouse (punto "tirado hacia atras")

    El pajaro debe lanzarse en la direccion OPUESTA al arrastre, asi que
    el angulo del impulso es el del vector (end_point -> start_point), y
    la magnitud del impulso es la distancia entre ambos puntos.

    Esquema:

        start (clic)  *<------ arrastre ------ * end (soltar)
                       ----lanzamiento---->

    Use las dos funciones definidas arriba en esta implementacion.
    """
    ### ---------------------- ###
    ### SU IMPLEMENTACION AQUI ###
    ### ---------------------- ###
    # El angulo va de end_point hacia start_point (direccion opuesta al arrastre)
    angle = get_angle_radians(end_point, start_point)
    # La magnitud del impulso es la distancia entre ambos puntos
    impulse = get_distance(start_point, end_point)
    logger.debug(f"ImpulseVector -> angle={math.degrees(angle):.1f} deg, impulse={impulse:.1f} px")
    return ImpulseVector(angle, impulse)