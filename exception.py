class CompileError(Exception):
    def __init__(self, message):
        self.message = message


class LanguageNotFoundError(Exception):
    pass


class InvalidRequestError(Exception):
    pass
