import os
import typing


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


class Struct:
    """dna.Struct is a C-type structure stored in the DNA."""

    def __init__(self, dna_type_id: bytes):
        self.dna_type_id = dna_type_id
        self._fields = []
        self._fields_by_name = {}

    def __repr__(self):
        return '%s(%r)' % (type(self).__qualname__, self.dna_type_id)

    def append_field(self, field: Field):
        self._fields.append(field)
        self._fields_by_name[field.name.name_only] = field

    def field_from_path(self,
                        pointer_size: int,
                        path: typing.Union[bytes, typing.Iterable[typing.Union[bytes, int]]]) \
            -> typing.Tuple[typing.Optional[Field], int]:
        """
        Support lookups as bytes or a tuple of bytes and optional index.

        C style 'id.name'   -->  (b'id', b'name')
        C style 'array[4]'  -->  (b'array', 4)

        :returns: the field itself, and its offset taking into account the optional index.
        """
        if isinstance(path, (tuple, list)):
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
        # fileobj.seek(field.offset, os.SEEK_CUR)
        if index:
            if field.name.is_pointer:
                index_offset = pointer_size * index
            else:
                index_offset = field.dna_type.size * index
            if index_offset >= field.size:
                raise OverflowError('path %r is out of bounds of its DNA type' % path)
            # fileobj.seek(index_offset, os.SEEK_CUR)
            offset += index_offset
        return field, offset

    def field_get(self, header, handle, path,
                  default=...,
                  use_nil=True, use_str=True,
                  ):
        field = self.field_from_path(header, handle, path)
        if field is None:
            if default is not ...:
                return default
            else:
                raise KeyError("%r not found in %r (%r)" %
                               (
                                   path, [f.dna_name.name_only for f in self._fields],
                                   self.dna_type_id))

        dna_type = field.dna_type
        dna_name = field.dna_name
        dna_size = field.dna_size

        if dna_name.is_pointer:
            return DNA_IO.read_pointer(handle, header)
        elif dna_type.dna_type_id == b'int':
            if dna_name.array_size > 1:
                return [DNA_IO.read_int(handle, header) for i in range(dna_name.array_size)]
            return DNA_IO.read_int(handle, header)
        elif dna_type.dna_type_id == b'short':
            if dna_name.array_size > 1:
                return [DNA_IO.read_short(handle, header) for i in range(dna_name.array_size)]
            return DNA_IO.read_short(handle, header)
        elif dna_type.dna_type_id == b'uint64_t':
            if dna_name.array_size > 1:
                return [DNA_IO.read_ulong(handle, header) for i in range(dna_name.array_size)]
            return DNA_IO.read_ulong(handle, header)
        elif dna_type.dna_type_id == b'float':
            if dna_name.array_size > 1:
                return [DNA_IO.read_float(handle, header) for i in range(dna_name.array_size)]
            return DNA_IO.read_float(handle, header)
        elif dna_type.dna_type_id == b'char':
            if dna_size == 1:
                # Single char, assume it's bitflag or int value, and not a string/bytes data...
                return DNA_IO.read_char(handle, header)
            if use_str:
                if use_nil:
                    return DNA_IO.read_string0(handle, dna_name.array_size)
                else:
                    return DNA_IO.read_string(handle, dna_name.array_size)
            else:
                if use_nil:
                    return DNA_IO.read_bytes0(handle, dna_name.array_size)
                else:
                    return DNA_IO.read_bytes(handle, dna_name.array_size)
        else:
            raise NotImplementedError("%r exists but isn't pointer, can't resolve field %r" %
                                      (path, dna_name.name_only), dna_name, dna_type)

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
