import unittest

import shapes


class TestShapes(unittest.TestCase):
    def test_rect(self):
        self.assertEqual(shapes.rect_area(3, 4), 12)

    def test_square(self):
        self.assertEqual(shapes.square_area(5), 25)

    def test_circle(self):
        self.assertAlmostEqual(shapes.circle_area(1), 3.141592653589793)

    def test_triangle(self):
        # shapes.py 還沒有這個函式，所以這條是紅的
        self.assertEqual(shapes.triangle_area(6, 4), 12)


if __name__ == "__main__":
    unittest.main()
