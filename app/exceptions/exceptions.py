class AppError(Exception):
    def __init__(self, name: str, message: str, status_code: int = 400) -> None:
        self.name = name
        self.message = message
        self.status_code = status_code
