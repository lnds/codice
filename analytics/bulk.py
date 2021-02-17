
class BulkOperationManager(object):

    def __init__(self, model_class, chunk_size=500):
        self._chunk = list()
        self._model_class = model_class
        self.chunk_size = chunk_size

    def _commit(self):
        pass

    def add(self, obj):
        """ :return True if _commit is called"""
        self._chunk.append(obj)
        if len(self._chunk) >= self.chunk_size:
            self._commit()
            return True
        return False

    def done(self):
        if len(self._chunk) > 0:
            self._commit()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.done()


class BulkCreateManager(BulkOperationManager):

    def _commit(self):
        self._model_class.objects.bulk_create(self._chunk)
        self._chunk = []


class BulkUpdateManager(BulkOperationManager):

    def __init__(self,model_class, fields, chunk_size=500):
        super().__init__(model_class, chunk_size)
        self._fields = fields

    def _commit(self):
        self._model_class.objects.bulk_update(self._chunk, self._fields)
        self._chunk = []

