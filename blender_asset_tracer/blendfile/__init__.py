# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
# (c) 2009, At Mind B.V. - Jeroen Bakker
# (c) 2014, Blender Foundation - Campbell Barton
# (c) 2018, Blender Foundation - Sybren A. Stüvel

import collections
import gzip
import logging
import os
import struct
import pathlib
import tempfile
import typing

from . import exceptions, dna_io, dna, header

log = logging.getLogger(__name__)

FILE_BUFFER_SIZE = 1024 * 1024

BLENDFILE_MAGIC = b'BLENDER'
GZIP_MAGIC = b'\x1f\x8b'


def pad_up_4(offset):
    return (offset + 3) & ~3


class BlendFile:
    """Representation of a blend file.

    :ivar filepath: which file this object represents.
    :ivar raw_filepath: which file is accessed; same as filepath for
        uncompressed files, but a temporary file for compressed files.
    :ivar fileobj: the file object that's being accessed.
    """
    log = log.getChild('BlendFile')

    def __init__(self, path: pathlib.Path, mode='rb'):
        """Create a BlendFile instance for the blend file at the path.

        Opens the file for reading or writing pending on the access. Compressed
        blend files are uncompressed to a temporary location before opening.

        :param path: the file to open
        :param mode: see mode description of pathlib.Path.open()
        """
        self.filepath = path
        self._is_modified = False

        fileobj = path.open(mode, buffering=FILE_BUFFER_SIZE)
        magic = fileobj.read(len(BLENDFILE_MAGIC))

        if magic == BLENDFILE_MAGIC:
            self.is_compressed = False
            self.raw_filepath = path
            self.fileobj = fileobj
        elif magic[:2] == GZIP_MAGIC:
            self.is_compressed = True

            log.debug("compressed blendfile detected: %s", path)
            # Decompress to a temporary file.
            tmpfile = tempfile.NamedTemporaryFile()
            fileobj.seek(0, os.SEEK_SET)
            with gzip.GzipFile(fileobj=fileobj, mode=mode) as gzfile:
                magic = gzfile.read(len(BLENDFILE_MAGIC))
                if magic != BLENDFILE_MAGIC:
                    raise exceptions.BlendFileError("Compressed file is not a blend file", path)

                data = magic
                while data:
                    tmpfile.write(data)
                    data = gzfile.read(FILE_BUFFER_SIZE)

            # Further interaction should be done with the uncompressed file.
            self.raw_filepath = pathlib.Path(tmpfile.name)
            fileobj.close()
            self.fileobj = tmpfile
        elif magic != BLENDFILE_MAGIC:
            raise exceptions.BlendFileError("File is not a blend file", path)

        self.header = header.BlendFileHeader(self.fileobj, self.raw_filepath)
        self.block_header_struct = self.header.create_block_header_struct()
        self.blocks = []
        self.code_index = collections.defaultdict(list)
        self.structs = []
        self.sdna_index_from_id = {}
        self.block_from_addr = {}

        self._load_blocks()

    def _load_blocks(self):
        """Read the blend file to load its DNA structure to memory."""
        while True:
            block = BlendFileBlock(self)
            if block.code == b'ENDB':
                break

            if block.code == b'DNA1':
                self.structs, self.sdna_index_from_id = self.decode_structs(block)
            else:
                self.fileobj.seek(block.size, os.SEEK_CUR)

            self.blocks.append(block)
            self.code_index[block.code].append(block)
            self.block_from_addr[block.addr_old] = block

        if not self.structs:
            raise exceptions.NoDNA1Block("No DNA1 block in file, not a valid .blend file",
                                         self.filepath)

    def __repr__(self):
        clsname = self.__class__.__qualname__
        if self.filepath == self.raw_filepath:
            return '<%s %r>' % (clsname, self.filepath)
        return '<%s %r reading from %r>' % (clsname, self.filepath, self.raw_filepath)

    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, traceback):
        self.close()

    @property
    def is_modified(self) -> bool:
        return self._is_modified

    def mark_modified(self):
        """Recompess the file when it is closed."""
        self.log.debug('Marking %s as modified', self.raw_filepath)
        self._is_modified = True

    def find_blocks_from_code(self, code: bytes) -> typing.List['BlendFileBlock']:
        assert isinstance(code, bytes)
        return self.code_index[code]

    def find_block_from_address(self, address: int) -> typing.Optional['BlendFileBlock']:
        """Return the block at that address, or None if not found.

        :param address: the BlendFileBlock.addr_old value
        """
        assert type(address) is int
        return self.block_from_addr.get(address)

    def close(self):
        """Close the blend file.

        Recompresses the blend file if it was compressed and changed.
        """
        if not self.fileobj:
            return

        if self._is_modified and self.is_compressed:
            log.debug("recompressing modified blend file %s", self.raw_filepath)
            self.fileobj.seek(os.SEEK_SET, 0)

            with gzip.open(self.filepath, 'wb') as gzfile:
                while True:
                    data = self.fileobj.read(FILE_BUFFER_SIZE)
                    if not data:
                        break
                    gzfile.write(data)
            log.debug("compressing to %s finished", self.filepath)

        # Close the file object after recompressing, as it may be a temporary
        # file that'll disappear as soon as we close it.
        self.fileobj.close()
        self._is_modified = False

    def ensure_subtype_smaller(self, sdna_index_curr, sdna_index_next):
        # never refine to a smaller type
        curr_struct = self.structs[sdna_index_curr]
        next_struct = self.structs[sdna_index_next]
        if curr_struct.size > next_struct.size:
            raise RuntimeError("Can't refine to smaller type (%s -> %s)" %
                               (curr_struct.dna_type_id.decode('utf-8'),
                                next_struct.dna_type_id.decode('utf-8')))

    def decode_structs(self, block: 'BlendFileBlock'):
        """
        DNACatalog is a catalog of all information in the DNA1 file-block
        """
        self.log.debug("building DNA catalog")
        endian = self.header.endian
        shortstruct = endian.USHORT
        shortstruct2 = endian.USHORT2
        intstruct = endian.UINT
        assert intstruct.size == 4

        data = self.fileobj.read(block.size)
        types = []
        typenames = []
        structs = []
        sdna_index_from_id = {}

        offset = 8
        names_len = intstruct.unpack_from(data, offset)[0]
        offset += 4

        self.log.debug("building #%d names" % names_len)
        for _ in range(names_len):
            typename = endian.read_data0_offset(data, offset)
            offset = offset + len(typename) + 1
            typenames.append(dna.Name(typename))

        offset = pad_up_4(offset)
        offset += 4
        types_len = intstruct.unpack_from(data, offset)[0]
        offset += 4
        self.log.debug("building #%d types" % types_len)
        for _ in range(types_len):
            dna_type_id = endian.read_data0_offset(data, offset)
            types.append(dna.Struct(dna_type_id))
            offset += len(dna_type_id) + 1

        offset = pad_up_4(offset)
        offset += 4
        self.log.debug("building #%d type-lengths" % types_len)
        for i in range(types_len):
            typelen = shortstruct.unpack_from(data, offset)[0]
            offset = offset + 2
            types[i].size = typelen

        offset = pad_up_4(offset)
        offset += 4

        structs_len = intstruct.unpack_from(data, offset)[0]
        offset += 4
        log.debug("building #%d structures" % structs_len)
        pointer_size = self.header.pointer_size
        for sdna_index in range(structs_len):
            struct_type_index, fields_len = shortstruct2.unpack_from(data, offset)
            offset += 4

            dna_struct = types[struct_type_index]
            sdna_index_from_id[dna_struct.dna_type_id] = sdna_index
            structs.append(dna_struct)

            dna_offset = 0

            for field_index in range(fields_len):
                field_type_index, field_name_index = shortstruct2.unpack_from(data, offset)
                offset += 4

                dna_type = types[field_type_index]
                dna_name = typenames[field_name_index]

                if dna_name.is_pointer or dna_name.is_method_pointer:
                    dna_size = pointer_size * dna_name.array_size
                else:
                    dna_size = dna_type.size * dna_name.array_size

                field = dna.Field(dna_type, dna_name, dna_size, dna_offset)
                dna_struct.append_field(field)
                dna_offset += dna_size

        return structs, sdna_index_from_id


class BlendFileBlock:
    """
    Instance of a struct.
    """
    log = log.getChild('BlendFileBlock')
    old_structure = struct.Struct(b'4sI')
    """old blend files ENDB block structure"""

    def __init__(self, bfile: BlendFile):
        self.bfile = bfile

        # Defaults; actual values are set by interpreting the block header.
        self.code = b''
        self.size = 0
        self.addr_old = 0
        self.sdna_index = 0
        self.count = 0
        self.file_offset = 0
        """Offset in bytes from start of file to beginning of the data block.

        Points to the data after the block header.
        """
        self.endian = bfile.header.endian

        header_struct = bfile.block_header_struct
        data = bfile.fileobj.read(header_struct.size)
        if len(data) != header_struct.size:
            self.log.warning("Blend file %s seems to be truncated, "
                             "expected %d bytes but could read only %d",
                             header_struct.size, len(data))
            self.code = b'ENDB'
            return

        # header size can be 8, 20, or 24 bytes long
        # 8: old blend files ENDB block (exception)
        # 20: normal headers 32 bit platform
        # 24: normal headers 64 bit platform
        if len(data) <= 15:
            self.log.debug('interpreting block as old-style ENB block')
            blockheader = self.old_structure.unpack(data)
            self.code = self.endian.read_data0(blockheader[0])
            return

        blockheader = header_struct.unpack(data)
        self.code = self.endian.read_data0(blockheader[0])
        if self.code != b'ENDB':
            self.size = blockheader[1]
            self.addr_old = blockheader[2]
            self.sdna_index = blockheader[3]
            self.count = blockheader[4]
            self.file_offset = bfile.fileobj.tell()

    def __repr__(self):
        return "<%s.%s (%s), size=%d at %s>" % (
            self.__class__.__name__,
            self.dna_type_name,
            self.code.decode(),
            self.size,
            hex(self.addr_old),
        )

    @property
    def dna_type(self) -> dna.Struct:
        return self.bfile.structs[self.sdna_index]

    @property
    def dna_type_name(self) -> str:
        return self.dna_type.dna_type_id.decode('ascii')

    def refine_type_from_index(self, sdna_index: int):
        """Change the DNA Struct associated with this block.

        Use to make a block type more specific, for example when you have a
        modifier but need to access it as SubSurfModifier.

        :param sdna_index: the SDNA index of the DNA type.
        """
        assert type(sdna_index) is int
        sdna_index_curr = self.sdna_index
        self.bfile.ensure_subtype_smaller(sdna_index_curr, sdna_index)
        self.sdna_index = sdna_index

    def refine_type(self, dna_type_id: bytes):
        """Change the DNA Struct associated with this block.

        Use to make a block type more specific, for example when you have a
        modifier but need to access it as SubSurfModifier.

        :param dna_type_id: the name of the DNA type.
        """
        assert isinstance(dna_type_id, bytes)
        sdna_index = self.bfile.sdna_index_from_id[dna_type_id]
        self.refine_type_from_index(sdna_index)

    def get_file_offset(self, path: bytes) -> (int, int):  # TODO(Sybren): port to BAT
        """Return (offset, length)"""
        assert isinstance(path, bytes)

        # TODO: refactor to just return the length, and check whether this isn't actually
        # simply the same as self.size.
        ofs = self.file_offset
        field, _ = self.dna_type.field_from_path(self.bfile.header.pointer_size, path)
        return ofs, field.name.array_size

    def get(self,
            path: dna.FieldPath,
            default=...,
            null_terminated=True,
            as_str=True,
            base_index=0,
            ) -> typing.Any:
        """Read a property and return the value.

        :param path: name of the property (like `b'loc'`), tuple of names
            to read a sub-property (like `(b'id', b'name')`), or tuple of
            name and index to read one item from an array (like
            `(b'loc', 2)`)
        :param default: The value to return when the field does not exist.
            Use Ellipsis (the default value) to raise a KeyError instead.
        :param null_terminated: Only used when reading bytes or strings. When
            True, stops reading at the first zero byte; be careful with this
            when reading binary data.
        :param as_str: When True, automatically decode bytes to string
            (assumes UTF-8 encoding).
        """
        ofs = self.file_offset
        if base_index != 0:
            if base_index >= self.count:
                raise OverflowError('%r: index %d overflows size %d' %
                                    (self, base_index, self.count))
            ofs += (self.size // self.count) * base_index
        self.bfile.fileobj.seek(ofs, os.SEEK_SET)

        dna_struct = self.bfile.structs[self.sdna_index]
        return dna_struct.field_get(
            self.bfile.header, self.bfile.fileobj, path,
            default=default,
            null_terminated=null_terminated, as_str=as_str,
        )

    def get_recursive_iter(self,
                           path: dna.FieldPath,
                           path_root: dna.FieldPath = b'',
                           default=...,
                           null_terminated=True,
                           as_str=True,
                           base_index=0,
                           ) -> typing.Iterator[typing.Tuple[bytes, typing.Any]]:
        """Generator, yields (path, property value) tuples.

        If a property cannot be decoded, a string representing its DNA type
        name is used as its value instead, between pointy brackets.
        """
        if path_root:
            path_full = (
                    (path_root if type(path_root) is tuple else (path_root,)) +
                    (path if type(path) is tuple else (path,)))
        else:
            path_full = path

        try:
            # Try accessing as simple property
            yield (path_full,
                   self.get(path_full, default, null_terminated, as_str, base_index))
        except exceptions.NoReaderImplemented as ex:
            # This was not a simple property, so recurse into its DNA Struct.
            dna_type = ex.dna_type
            struct_index = self.bfile.sdna_index_from_id.get(dna_type.dna_type_id)
            if struct_index is None:
                yield (path_full, "<%s>" % dna_type.dna_type_id.decode('ascii'))
                return

            # Recurse through the fields.
            for f in dna_type.fields:
                yield from self.get_recursive_iter(f.name.name_only, path_full, default=default,
                                                   null_terminated=null_terminated, as_str=as_str)

    def get_data_hash(self):  # TODO(Sybren): port to BAT
        """
        Generates a 'hash' that can be used instead of addr_old as block id, and that should be 'stable' across .blend
        file load & save (i.e. it does not changes due to pointer addresses variations).
        """
        # TODO This implementation is most likely far from optimal... and CRC32 is not renown as the best hashing
        #      algo either. But for now does the job!
        import zlib
        def _is_pointer(self, k):
            return self.file.structs[self.sdna_index].field_from_path(
                self.file.header, self.file.handle, k).dna_name.is_pointer

        hsh = 1
        for k, v in self.items_recursive():
            if not _is_pointer(self, k):
                hsh = zlib.adler32(str(v).encode(), hsh)
        return hsh

    def set(self, path: dna.FieldPath, value):  # TODO(Sybren): port to BAT
        dna_struct = self.bfile.structs[self.sdna_index]
        self.bfile.mark_modified()
        self.bfile.fileobj.seek(self.file_offset, os.SEEK_SET)
        return dna_struct.field_set(self.bfile.header, self.bfile.fileobj, path, value)

    def get_pointer(
            self, path: dna.FieldPath,
            default=...,
            base_index=0,
    ) -> typing.Union[None, 'BlendFileBlock', typing.Any]:
        """Same as get() but dereferences a pointer.

        :raises exceptions.SegmentationFault: when there is no datablock with
            the pointed-to address.
        """
        result = self.get(path, default=default, base_index=base_index)

        # If it's not an integer, we have no pointer to follow and this may
        # actually be a non-pointer property.
        if type(result) is not int:
            return result

        if result == 0:
            return None

        try:
            return self.bfile.block_from_addr[result]
        except KeyError:
            raise exceptions.SegmentationFault('address does not exist', path, result)

    def __getitem__(self, path: dna.FieldPath):
        return self.get(path, as_str=False)

    def __setitem__(self, item, value):
        self.set(item, value)

    def keys(self) -> typing.Iterator[bytes]:
        """Generator, yields all field names of this block."""
        return (f.name.name_only for f in self.dna_type.fields)

    def values(self):
        for k in self.keys():
            try:
                yield self[k]
            except exceptions.NoReaderImplemented as ex:
                yield '<%s>' % ex.dna_type.dna_type_id.decode('ascii')

    def items(self):
        for k in self.keys():
            try:
                yield (k, self[k])
            except exceptions.NoReaderImplemented as ex:
                yield (k, '<%s>' % ex.dna_type.dna_type_id.decode('ascii'))

    def items_recursive(self):
        """Generator, yields (property path, property value) recursively for all properties."""
        for k in self.keys():
            yield from self.get_recursive_iter(k, as_str=False)
