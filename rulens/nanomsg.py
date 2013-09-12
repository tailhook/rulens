import ctypes.util
from itertools import count


def _rc_checker(rc, func, args):
    if rc == -1:
        raise OSError(ctypes.get_errno())
    return rc


lib = ctypes.CDLL(ctypes.util.find_library('nanomsg'))
NN_MSG = (1 << (8*ctypes.sizeof(ctypes.c_size_t))) - 1

lib.nn_symbol.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
lib.nn_symbol.restype = ctypes.c_char_p
lib.nn_socket.argtypes = [ctypes.c_int, ctypes.c_int]
lib.nn_socket.restype = ctypes.c_int
lib.nn_socket.errcheck = _rc_checker
lib.nn_recv.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64),
                        ctypes.c_size_t, ctypes.c_int]
lib.nn_recv.restype = ctypes.c_int
lib.nn_recv.errcheck = _rc_checker
lib.nn_send.argtypes = [ctypes.c_int, ctypes.c_char_p,
                        ctypes.c_size_t, ctypes.c_int]
lib.nn_send.restype = ctypes.c_int
lib.nn_send.errcheck = _rc_checker
lib.nn_bind.argtypes = [ctypes.c_int, ctypes.c_char_p]
lib.nn_bind.restype = ctypes.c_int
lib.nn_bind.errcheck = _rc_checker


class Const:

    def __init__(self):
        val = ctypes.c_int()
        for i in count():
            name = lib.nn_symbol(i, ctypes.byref(val))
            if name is None:
                break
            name = name.decode('ascii')
            if name.startswith('NN_'):
                name = name[3:]
            setattr(self, name, val.value)


const = Const()


def reply_service(bind, callback):
    ptr = ctypes.c_uint64()
    sock = lib.nn_socket(const.AF_SP, const.REP)
    lib.nn_bind(sock, bind.encode('ascii'))
    while True:
        rc = lib.nn_recv(sock, ctypes.byref(ptr), NN_MSG, 0)
        reply = callback(ctypes.string_at(ptr.value, rc))
        lib.nn_send(sock, reply, len(reply), 0)
