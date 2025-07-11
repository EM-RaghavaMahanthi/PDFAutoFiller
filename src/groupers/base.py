class BaseGrouper:
    def __init__(self, extracted_data: dict, **kwargs):
        self.extracted_data = extracted_data
        self.params = kwargs

    def group(self):
        raise NotImplementedError("Subclasses must implement the group() method.")
