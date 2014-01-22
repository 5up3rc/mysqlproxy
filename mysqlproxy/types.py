"""
Protocol wire types
"""
import struct
from StringIO import StringIO

def fixed_length_byte_val(size, inbytes):
    """
    Integer value of fixed length integer with size 
    `size` from raw bytes `inbytes`
    """
    inbytes = [b for b in inbytes]
    val = 0
    for i in range(0, size):
        val += ord(inbytes[i]) * (256 ** i)
    return val


class MySQLDataType(object):
    """
    Generic for a data type found in a payload
    """
    def __init__(self):
        self.val = None
        self.length = 0

    def read_in(self, fstream):
        """
        Read data in from stream
        """
        raise NotImplementedError

    def write_out(self, fstream):
        """
        Write relevant data to stream
        """
        raise NotImplementedError


class FixedLengthString(MySQLDataType):
    """
    String of a static length
    """
    def __init__(self, size, val = None):
        super(FixedLengthString, self).__init__()
        self.val = None
        self.length = size
        if val:
            if len(val) != size:
                raise ValueError('lolwut')
            self.val = val

    def read_in(self, fstream):
        self.val = fstream.read(self.length)
        return self.length

    def write_out(self, fstream):
        fstream.write(bytes(self.val))
        return self.length


class RestOfPacketString(MySQLDataType):
    """
    AKA the EOF string
    """
    def read_in(self, fde):
        """
        EOF strings read the rest of the packet
        """
        self.val = bytes(fde.read())
        self.length = len(self.val)

    def write_out(self, fde):
        """
        Write out
        """
        fde.write(bytes(self.val))


class NulTerminatedString(MySQLDataType):
    """
    Null-terminated C-style string
    """
    def __init__(self, val = None):
        super(NulTerminatedString, self).__init__()
        if val != None and type(val) != unicode:
            raise ValueError('NulTerminatedString initial val must be unicode')
        self.val = val

    def read_in(self, fstream):
        self.length = 0
        onebyte = bytes(fstream.read(1))
        while onebyte != b'\x00':
            self.val += onebyte
            self.length += 1
        return self.length

    def write_out(self, fstream):
        fstream.write(bytes(self.val) + '\x00')
        return self.length


class FixedLengthInteger(MySQLDataType):
    """
    Integer of static size
    """
    def __init__(self, size, val=0):
        super(FixedLengthInteger, self).__init__()
        self.length = size
        self.val = val

    def read_in(self, fstream):
        self.val = fixed_length_byte_val(self.length, fstream.read(self.length))

    def write_out(self, fstream=None):
        val = self.val
        mbytes = b''
        for _ in range(0, self.length):
            mbytes += bytes(chr(val & 255))
            val >>= 8
        if fstream:
            fstream.write(mbytes)
            return len(mbytes)
        else:
            return mbytes


class LengthEncodedInteger(MySQLDataType):
    """
    Integer with the length given
    """
    def __init__(self, val):
        super(LengthEncodedInteger, self).__init__()
        self.val = val
        if val:
            # stupidly calculate length
            sio = StringIO()
            self.write_out(sio)
            self.length = sio.len
        else:
            self.length = 0

    def read_in(self, fstream):
        sentinel = ord(fstream.read(1))
        read_amt = 0
        if sentinel < 0xfb:
            self.val = sentinel
            read_amt = 1
        elif sentinel == 0xfc:
            self.val, = struct.unpack('<H', fstream.read(2))
            read_amt = 3
        elif sentinel == 0xfd:
            self.val, = struct.unpack('<L', fstream.read(3) + '\x00')
            read_amt = 4
        elif sentinel == 0xfe:
            self.val, = struct.unpack('<L', fstream.read(4))
            read_amt = 5
        self.length = read_amt
        return read_amt

    def write_out(self, fstream):
        write_buf = b''
        if self.val < 251:
            write_buf += bytes(chr(self.val))
        elif self.val >= 251 and self.val < 2**16:
            write_buf += bytes(chr(0xfc) + struct.pack('<H', self.val))
        elif self.val >= 2**16 and self.val < 2**24:
            write_buf += bytes(chr(0xfd) + struct.pack('<L', self.val)[:3])
        elif self.val >= 2**24 and self.val < 2**64:
            write_buf += bytes(chr(0xfe) + struct.pack('<Q', self.val))
        fstream.write(write_buf)
        return len(write_buf)
