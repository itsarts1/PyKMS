__all__ = ['encode']
# from source of pypy:
# pypy / pypy / module / _codecs / interp_codecs.py
# pypy / rpython / rlib / runicode.py
import sys

BYTEORDER = sys.byteorder
BYTEORDER2 = BYTEORDER[0] + 'e'      # either "le" or "be"
assert BYTEORDER2 in ('le', 'be')


def _storechar(result, CH, byteorder):
    hi = ((CH) >> 8) & 0xff
    lo = (CH) & 0xff
    if byteorder == 'little':
        result.append(lo)
        result.append(hi)
    else:
        result.append(hi)
        result.append(lo)

def encode_utf_16(s, errors,
                          errorhandler=None,
                          allow_surrogates=True,
                          byteorder='little',
                          public_encoding_name='utf16'):
    if errorhandler is None:
        pass
        # errorhandler = default_unicode_error_encode

    result = bytearray()
    if byteorder == 'native':
        _storechar(result, 0xFEFF, BYTEORDER)
        byteorder = BYTEORDER

    for pos, c in enumerate(s):
        ch = ord(c)

        if ch < 0xD800:
            _storechar(result, ch, byteorder)
        elif ch >= 0x10000:
            _storechar(result, 0xD800 | ((ch-0x10000) >> 10), byteorder)
            _storechar(result, 0xDC00 | ((ch-0x10000) & 0x3FF), byteorder)
        elif ch >= 0xE000 or allow_surrogates:
            _storechar(result, ch, byteorder)
        else:
            ru, rs, pos = errorhandler(errors, public_encoding_name,
                                       'surrogates not allowed',
                                       s, pos-1, pos)
            if rs is not None:
                # py3k only
                if len(rs) % 2 != 0:
                    errorhandler('strict', public_encoding_name,
                                 'surrogates not allowed',
                                 s, pos-1, pos)
                result.append(rs)
                continue
            for ch in ru:
                if ord(ch) < 0xD800:
                    _storechar(result, ord(ch), byteorder)
                else:
                    errorhandler('strict', public_encoding_name,
                                 'surrogates not allowed',
                                 s, pos-1, pos)
            continue

    return bytes(result)

def encode(obj, encoding='utf_8', errors='strict'):
    if encoding == 'utf_8':
        return obj.encode(encoding, errors)
    elif encoding == 'utf_16':
        return encode_utf_16(obj, [], None,
                             True, 'native',
                             'utf-16-' + BYTEORDER2)
    elif encoding == 'utf_16_be':
        return encode_utf_16(obj, [], None,
                             True, 'big',
                             'utf-16-be')
    elif encoding == 'utf_16_le':
        return encode_utf_16(obj, [], None,
                             True, 'little',
                             'utf-16-le')
    else:
        raise NotImplementedError('Encoding of {} not implemented'.format(encoding))
