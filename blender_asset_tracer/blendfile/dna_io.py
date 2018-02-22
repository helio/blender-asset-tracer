"""Read-write utility functions."""

import struct
import typing


class EndianIO:
    UCHAR = struct.Struct(b'<B')
    USHORT = struct.Struct(b'<H')
    USHORT2 = struct.Struct(b'<HH')  # two shorts in a row
    SSHORT = struct.Struct(b'<h')
    UINT = struct.Struct(b'<I')
    SINT = struct.Struct(b'<i')
    FLOAT = struct.Struct(b'<f')
    ULONG = struct.Struct(b'<Q')

    @classmethod
    def _read(cls, fileobj: typing.BinaryIO, typestruct: struct.Struct):
        data = fileobj.read(typestruct.size)
        return typestruct.unpack(data)[0]

    @classmethod
    def read_char(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.UCHAR)

    @classmethod
    def read_ushort(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.USHORT)

    @classmethod
    def read_short(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.SSHORT)

    @classmethod
    def read_uint(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.UINT)

    @classmethod
    def read_int(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.SINT)

    @classmethod
    def read_float(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.FLOAT)

    @classmethod
    def read_ulong(cls, fileobj: typing.BinaryIO):
        return cls._read(fileobj, cls.ULONG)

    @classmethod
    def read_pointer(cls, fileobj: typing.BinaryIO, pointer_size: int):
        """Read a pointer from a file."""

        if pointer_size == 4:
            return cls.read_uint(fileobj)
        if pointer_size == 8:
            return cls.read_ulong(fileobj)
        raise ValueError('unsupported pointer size %d' % pointer_size)

    @classmethod
    def write_string(cls, fileobj: typing.BinaryIO, astring: str, fieldlen: int):
        assert isinstance(astring, str)
        # TODO: truncate the string on a UTF-8 character boundary to avoid creating invalid UTF-8.
        cls.write_bytes(fileobj, astring.encode('utf-8'), fieldlen)

    @classmethod
    def write_bytes(cls, fileobj: typing.BinaryIO, data: bytes, fieldlen: int):
        assert isinstance(data, (bytes, bytearray))
        if len(data) >= fieldlen:
            to_write = data[0:fieldlen]
        else:
            to_write = data + b'\0'

        fileobj.write(to_write)

    @classmethod
    def read_bytes0(cls, fileobj, length):
        data = fileobj.read(length)
        return cls.read_data0(data)

    @classmethod
    def read_data0_offset(cls, data, offset):
        add = data.find(b'\0', offset) - offset
        return data[offset:offset + add]

    @classmethod
    def read_data0(cls, data):
        add = data.find(b'\0')
        if add < 0:
            return data
        return data[:add]


class LittleEndianTypes(EndianIO):
    pass


class BigEndianTypes(LittleEndianTypes):
    UCHAR = struct.Struct(b'>B')
    USHORT = struct.Struct(b'>H')
    USHORT2 = struct.Struct(b'>HH')  # two shorts in a row
    SSHORT = struct.Struct(b'>h')
    UINT = struct.Struct(b'>I')
    SINT = struct.Struct(b'>i')
    FLOAT = struct.Struct(b'>f')
    ULONG = struct.Struct(b'>Q')
