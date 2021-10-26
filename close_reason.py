from abc import abstractmethod, ABCMeta


class CloseReason(metaclass=ABCMeta):
    @abstractmethod
    def get_message(self):
        pass


class ClosedByProgramTermination(CloseReason):
    def __init__(self, code):
        self.code = code

    def get_message(self):
        return {'type': 'terminated', 'code': self.code}


class ClosedBySessionTimeout(CloseReason):
    def get_message(self):
        return {'type': 'timeout'}


class ClosedByWebSocketConnectionTimeout(CloseReason):
    def get_message(self):
        return {'type': 'connection_timeout'}
