from abc import abstractmethod, ABCMeta


class CloseReason(metaclass=ABCMeta):
    @abstractmethod
    def get_message(self):
        pass


class ClosedByCompileError(CloseReason):
    def __init__(self, out):
        self.out = out

    def get_message(self):
        return {'type': 'compile_error', 'out': self.out}


class ClosedByProgramTermination(CloseReason):
    def __init__(self, code):
        self.code = code

    def get_message(self):
        return {'type': 'terminated', 'code': self.code}


class ClosedBySessionTimeout(CloseReason):
    def get_message(self):
        return {'type': 'timeout'}


class ClosedByClientDisconnect(CloseReason):
    def get_message(self):
        return None


class ClosedByInvalidRequest(CloseReason):
    def get_message(self):
        return None
