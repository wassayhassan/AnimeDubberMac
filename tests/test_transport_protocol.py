from __future__ import annotations

import json
import unittest

from anime_dubber.transport.protocol import (
    decode_request,
    encode_message,
    response_error,
    response_ok,
)


class TransportProtocolTests(unittest.TestCase):
    def test_request_round_trip(self):
        line = json.dumps({
            "type": "request",
            "id": "42",
            "method": "hello",
            "params": {},
        })
        request = decode_request(line)
        self.assertEqual(request["id"], "42")
        self.assertEqual(request["method"], "hello")

    def test_request_requires_id(self):
        with self.assertRaises(ValueError):
            decode_request('{"type":"request","method":"hello"}')

    def test_encode_is_single_line_json(self):
        encoded = encode_message({"message": "a\nb"})
        self.assertNotIn("\n", encoded)
        self.assertEqual(json.loads(encoded)["message"], "a\nb")

    def test_response_shapes(self):
        ok = response_ok("1", {"hello": "world"})
        err = response_error("2", "bad", "ValueError")
        self.assertTrue(ok["ok"])
        self.assertFalse(err["ok"])
        self.assertEqual(err["error"]["type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
