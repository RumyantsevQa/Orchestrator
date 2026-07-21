from abc import ABC, abstractmethod


class ContextProvider(ABC):

    @abstractmethod
    def get_context(self) -> str:
        pass