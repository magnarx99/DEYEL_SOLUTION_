"""Error controlado con código HTTP y mensaje en español para el usuario."""


class ErrorApp(Exception):
    def __init__(self, status, mensaje, detalles=None):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje
        self.detalles = detalles  # p. ej. {'campo': 'mensaje'} para errores de validación
