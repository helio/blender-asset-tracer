import typing

import os

from . import dna_io, header, exceptions

# Either a simple path b'propname', or a tuple (b'parentprop', b'actualprop', arrayindex)
FieldPath = typing.Union[bytes, typing.Iterable[typing.Union[bytes, int]]]


class Name:
    """dna.Name is a C-type name stored in the DNA as bytes."""

    def __init__(self, name_full: bytes):
        self.name_full = name_full
        self.name_only = self.calc_name_only()
        self.is_pointer = self.calc_is_pointer()
        self.is_method_pointer = self.calc_is_method_pointer()
        self.array_size = self.calc_array_size()

    def __repr__(self):
        return '%s(%r)' % (type(self).__qualname__, self.name_full)

    def as_reference(self, parent) -> bytes:
        if not parent:
            return self.name_only
        return parent + b'.' + self.name_only

    def calc_name_only(self) -> bytes:
        result = self.name_full.strip(b'*()')
        index = result.find(b'[')
        if index == -1:
            return result
        return result[:index]

    def calc_is_pointer(self) -> bool:
        return b'*' in self.name_full

    def calc_is_method_pointer(self):
        return b'(*' in self.name_full

    def calc_array_size(self):
        result = 1
        partial_name = self.name_full

        while True:
            idx_start = partial_name.find(b'[')
            if idx_start < 0:
                break

            idx_stop = partial_name.find(b']')
            result *= int(partial_name[idx_start + 1:idx_stop])
            partial_name = partial_name[idx_stop + 1:]

        return result


class Field:
    """dna.Field is a coupled dna.Struct and dna.Name.

    It also contains the file offset in bytes.

    :ivar name: the name of the field.
    :ivar dna_type: the type of the field.
    :ivar size: size of the field on disk, in bytes.
    :ivar offset: cached offset of the field, in bytes.
    """

    def __init__(self,
                 dna_type: 'Struct',
                 name: Name,
                 size: int,
                 offset: int):
        self.dna_type = dna_type
        self.name = name
        self.size = size
        self.offset = offset

    def __repr__(self):
        return '<%r %r (%s)>' % (type(self).__qualname__, self.name, self.dna_type)


class Struct:
    """dna.Struct is a C-type structure stored in the DNA."""

    def __init__(self, dna_type_id: bytes, size: int = None):
        """
        :param dna_type_id: name of the struct in C, like b'AlembicObjectPath'.
        :param size: only for unit tests; typically set after construction by
            BlendFile.decode_structs(). If not set, it is calculated on the fly
            when struct.size is evaluated, based on the available fields.
        """
        self.dna_type_id = dna_type_id
        self._size = size
        self._fields = []
        self._fields_by_name = {}

    def __repr__(self):
        return '%s(%r)' % (type(self).__qualname__, self.dna_type_id)

    @property
    def size(self) -> int:
        if self._size is None:
            if not self._fields:
                raise ValueError('Unable to determine size of fieldless %r' % self)
            last_field = max(self._fields, key=lambda f: f.offset)
            self._size = last_field.offset + last_field.size
        return self._size

    @size.setter
    def size(self, new_size: int):
        self._size = new_size

    def append_field(self, field: Field):
        self._fields.append(field)
        self._fields_by_name[field.name.name_only] = field

    @property
    def fields(self) -> typing.List[Field]:
        """Return the fields of this Struct.

        Do not modify the returned list; use append_field() instead.
        """
        return self._fields

    def field_from_path(self,
                        pointer_size: int,
                        path: FieldPath) \
            -> typing.Tuple[Field, int]:
        """
        Support lookups as bytes or a tuple of bytes and optional index.

        C style 'id.name'   -->  (b'id', b'name')
        C style 'array[4]'  -->  (b'array', 4)

        :returns: the field itself, and its offset taking into account the
            optional index. The offset is relative to the start of the struct,
            i.e. relative to the BlendFileBlock containing the data.
        :raises KeyError: if the field does not exist.
        """
        if isinstance(path, tuple):
            name = path[0]
            if len(path) >= 2 and not isinstance(path[1], bytes):
                name_tail = path[2:]
                index = path[1]
                assert isinstance(index, int)
            else:
                name_tail = path[1:]
                index = 0
        else:
            name = path
            name_tail = None
            index = 0

        if not isinstance(name, bytes):
            raise TypeError('name should be bytes, but is %r' % type(name))

        field = self._fields_by_name.get(name)
        if not field:
            raise KeyError('%r has no field %r, only %r' %
                           (self, name, sorted(self._fields_by_name.keys())))

        if name_tail:
            return field.dna_type.field_from_path(pointer_size, name_tail)

        offset = field.offset
        if index:
            if field.name.is_pointer:
                index_offset = pointer_size * index
            else:
                index_offset = field.dna_type.size * index
            if index_offset >= field.size:
                raise OverflowError('path %r is out of bounds of its DNA type %s' %
                                    (path, field.dna_type))
            offset += index_offset

        return field, offset

    def field_get(self,
                  file_header: header.BlendFileHeader,
                  fileobj: typing.BinaryIO,
                  path: FieldPath,
                  default=...,
                  null_terminated=True,
                  as_str=True,
                  ):
        """Read the value of the field from the blend file.

        Assumes the file pointer of `fileobj` is seek()ed to the start of the
        struct on disk (e.g. the start of the BlendFileBlock containing the
        data).

        :param file_header:
        :param fileobj:
        :param path:
        :param default: The value to return when the field does not exist.
            Use Ellipsis (the default value) to raise a KeyError instead.
        :param null_terminated: Only used when reading bytes or strings. When
            True, stops reading at the first zero byte. Be careful with this
            default when reading binary data.
        :param as_str: When True, automatically decode bytes to string
            (assumes UTF-8 encoding).
        """
        try:
            field, offset = self.field_from_path(file_header.pointer_size, path)
        except KeyError:
            if default is ...:
                raise
            return default

        fileobj.seek(offset, os.SEEK_CUR)

        dna_type = field.dna_type
        dna_name = field.name
        types = file_header.endian

        # Some special cases (pointers, strings/bytes)
        if dna_name.is_pointer:
            return types.read_pointer(fileobj, file_header.pointer_size)
        if dna_type.dna_type_id == b'char':
            if field.size == 1:
                # Single char, assume it's bitflag or int value, and not a string/bytes data...
                return types.read_char(fileobj)
            if null_terminated or (null_terminated is None and as_str):
                data = types.read_bytes0(fileobj, dna_name.array_size)
            else:
                data = fileobj.read(dna_name.array_size)

            if as_str:
                return data.decode('utf8')
            return data

        simple_readers = {
            b'int': types.read_int,
            b'short': types.read_short,
            b'uint64_t': types.read_ulong,
            b'float': types.read_float,
        }
        try:
            simple_reader = simple_readers[dna_type.dna_type_id]
        except KeyError:
            raise exceptions.NoReaderImplemented(
                "%r exists but not simple type (%r), can't resolve field %r" %
                (path, dna_type.dna_type_id.decode(), dna_name.name_only),
                dna_name, dna_type) from None

        if isinstance(path, tuple) and len(path) > 1 and isinstance(path[-1], int):
            # The caller wants to get a single item from an array. The offset we seeked to already
            # points to this item. In this case we do not want to look at dna_name.array_size,
            # because we want a single item from that array.
            return simple_reader(fileobj)

        if dna_name.array_size > 1:
            return [simple_reader(fileobj) for _ in range(dna_name.array_size)]
        return simple_reader(fileobj)

    def field_set(self, header, handle, path, value):
        assert (type(path) == bytes)

        field = self.field_from_path(header, handle, path)
        if field is None:
            raise KeyError("%r not found in %r" %
                           (path, [f.dna_name.name_only for f in self.fields]))

        dna_type = field.dna_type
        dna_name = field.dna_name

        if dna_type.dna_type_id == b'char':
            if type(value) is str:
                return DNA_IO.write_string(handle, value, dna_name.array_size)
            else:
                return DNA_IO.write_bytes(handle, value, dna_name.array_size)
        else:
            raise NotImplementedError("Setting %r is not yet supported for %r" %
                                      (dna_type, dna_name), dna_name, dna_type)
