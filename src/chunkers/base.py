from abc import ABC, abstractmethod

class BaseChunker(ABC):
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer