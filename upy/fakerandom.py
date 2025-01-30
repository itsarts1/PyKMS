from urandom import *
import math

def randint(a, b):
    while True:
        r = getrandbits(math.ceil(math.log2(b - a)))
        if r < b - a:
            break
    return a + r

def choice(seq):
    """Choose a random element from a non-empty sequence."""
    try:
        i = randint(0, len(seq))
    except ValueError:
        raise IndexError('Cannot choose from an empty sequence')
    return seq[i]
