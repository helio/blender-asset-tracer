import os
import struct


class DNAName:
    """
    DNAName is a C-type name stored in the DNA
    """
    __slots__ = (
        "name_full",
        "name_only",
        "is_pointer",
        "is_method_pointer",
        "array_size",
    )

    def __init__(self, name_full):
        self.name_full = name_full
        self.name_only = self.calc_name_only()
        self.is_pointer = self.calc_is_pointer()
        self.is_method_pointer = self.calc_is_method_pointer()
        self.array_size = self.calc_array_size()

    def __repr__(self):
        return '%s(%r)' % (type(self).__qualname__, self.name_full)

    def as_reference(self, parent):
        if parent is None:
            result = b''
        else:
            result = parent + b'.'

        result = result + self.name_only
        return result

    def calc_name_only(self):
        result = self.name_full.strip(b'*()')
        index = result.find(b'[')
        if index != -1:
            result = result[:index]
        return result

    def calc_is_pointer(self):
        return (b'*' in self.name_full)

    def calc_is_method_pointer(self):
        return (b'(*' in self.name_full)

    def calc_array_size(self):
        result = 1
        temp = self.name_full
        index = temp.find(b'[')

        while index != -1:
            index_2 = temp.find(b']')
            result *= int(temp[index + 1:index_2])
            temp = temp[index_2 + 1:]
            index = temp.find(b'[')

        return result


class DNAField:
    """
    DNAField is a coupled DNAStruct and DNAName
    and cache offset for reuse
    """
    __slots__ = (
        # DNAName
        "dna_name",
        # tuple of 3 items
        # [bytes (struct name), int (struct size), DNAStruct]
        "dna_type",
        # size on-disk
        "dna_size",
        # cached info (avoid looping over fields each time)
        "dna_offset",
    )

    def __init__(self, dna_type, dna_name, dna_size, dna_offset):
        self.dna_type = dna_type
        self.dna_name = dna_name
        self.dna_size = dna_size
        self.dna_offset = dna_offset


class DNAStruct:
    """
    DNAStruct is a C-type structure stored in the DNA
    """
    __slots__ = (
        "dna_type_id",
        "size",
        "fields",
        "field_from_name",
        "user_data",
    )

    def __init__(self, dna_type_id):
        self.dna_type_id = dna_type_id
        self.fields = []
        self.field_from_name = {}
        self.user_data = None

    def __repr__(self):
        return '%s(%r)' % (type(self).__qualname__, self.dna_type_id)

    def field_from_path(self, header, handle, path):
        """
        Support lookups as bytes or a tuple of bytes and optional index.

        C style 'id.name'   -->  (b'id', b'name')
        C style 'array[4]'  -->  ('array', 4)
        """
        if type(path) is tuple:
            name = path[0]
            if len(path) >= 2 and type(path[1]) is not bytes:
                name_tail = path[2:]
                index = path[1]
                assert (type(index) is int)
            else:
                name_tail = path[1:]
                index = 0
        else:
            name = path
            name_tail = None
            index = 0

        assert (type(name) is bytes)

        field = self.field_from_name.get(name)

        if field is not None:
            handle.seek(field.dna_offset, os.SEEK_CUR)
            if index != 0:
                if field.dna_name.is_pointer:
                    index_offset = header.pointer_size * index
                else:
                    index_offset = field.dna_type.size * index
                assert (index_offset < field.dna_size)
                handle.seek(index_offset, os.SEEK_CUR)
            if not name_tail:  # None or ()
                return field
            else:
                return field.dna_type.field_from_path(header, handle, name_tail)

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
                                   path, [f.dna_name.name_only for f in self.fields],
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

