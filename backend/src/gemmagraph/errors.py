class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class Cancelled(AppError):
    def __init__(self):
        super().__init__("cancelled", "运行已取消", 409)
