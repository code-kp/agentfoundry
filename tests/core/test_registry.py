import unittest

from core.registry import Register


class RegisterTest(unittest.TestCase):
    def tearDown(self) -> None:
        Register.clear()

    def test_register_and_get_round_trip(self) -> None:
        marker = object()

        Register.register(object, "marker", marker)

        self.assertIs(Register.get(object, "marker"), marker)
        self.assertIs(Register.maybe_get(object, "marker"), marker)

    def test_register_without_overwrite_rejects_duplicates(self) -> None:
        Register.register(str, "entry", "first")

        with self.assertRaises(KeyError):
            Register.register(str, "entry", "second", overwrite=False)


if __name__ == "__main__":
    unittest.main()
