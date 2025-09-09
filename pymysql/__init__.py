class DictCursor:
    pass

class Cursor:
    pass

class _Cursors:
    DictCursor = DictCursor
    Cursor = Cursor

cursors = _Cursors()


def connect(*args, **kwargs):
    raise RuntimeError("pymysql stub: no database available")
