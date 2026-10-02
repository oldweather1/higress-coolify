import socket
import struct
import unittest

from check_agenthub_gateway_network import parse_addresses, skip_name


class DNSParsingTests(unittest.TestCase):
    def response(self, flags=0x8180, identifier=27182):
        name = b"\x07gateway\x10discipline-agent\x04tech\x00"
        return (struct.pack("!6H", identifier, flags, 1, 1, 0, 0)
                + name + struct.pack("!HH", 1, 1) + b"\xc0\x0c"
                + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton("192.0.2.3"))

    def test_compressed_answer(self):
        self.assertEqual(parse_addresses(self.response(), 27182), ["192.0.2.3"])

    def test_mismatched_or_error_or_truncated_reply(self):
        for payload in (self.response(identifier=12), self.response(flags=0x8183),
                        self.response(flags=0x8380), self.response()[:-1], b"short"):
            with self.assertRaises((ValueError, IndexError, struct.error)):
                parse_addresses(payload, 27182)

    def test_bad_name_or_pointer(self):
        for payload in (b"\xc0", b"\x40", b"\x04abc"):
            with self.assertRaises((ValueError, IndexError)):
                skip_name(payload, 0)


if __name__ == "__main__":
    unittest.main()
