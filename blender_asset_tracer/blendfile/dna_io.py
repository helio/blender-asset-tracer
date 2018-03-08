"""Read-write utility functions."""

import struct
import typing


class EndianIO:
    # TODO(Sybren): note as UCHAR: struct.Struct = None and move actual structs to LittleEndianTypes
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
        try:
            return typestruct.unpack(data)[0]
        except struct.error as ex:
            raise struct.error('%s (read %d bytes)' % (ex, len(data))) from None

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
    def write_string(cls, fileobj: typing.BinaryIO, astring: str, fieldlen: int) -> int:
        """Write a (truncated) string as UTF-8.

        The string will always be written 0-terminated.

        :param fileobj: the file to write to.
        :param astring: the string to write.
        :param fieldlen: the field length in bytes.
        :returns: the number of bytes written.
        """
        assert isinstance(astring, str)
        encoded = astring.encode('utf-8')

        # Take into account we also need space for a trailing 0-byte.
        maxlen = fieldlen - 1

        if len(encoded) >= maxlen:
            encoded = encoded[:maxlen]

            # Keep stripping off the last byte until the string
            # is valid UTF-8 again.
            while True:
                try:
                    encoded.decode('utf8')
                except UnicodeDecodeError:
                    encoded = encoded[:-1]
                else:
                    break

        return fileobj.write(encoded + b'\0')

    @classmethod
    def write_bytes(cls, fileobj: typing.BinaryIO, data: bytes, fieldlen: int) -> int:
        """Write (truncated) bytes.

        When len(data) < fieldlen, a terminating b'\0' will be appended.

        :returns: the number of bytes written.
        """
        assert isinstance(data, (bytes, bytearray))
        if len(data) >= fieldlen:
            to_write = data[0:fieldlen]
        else:
            to_write = data + b'\0'

        return fileobj.write(to_write)

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
