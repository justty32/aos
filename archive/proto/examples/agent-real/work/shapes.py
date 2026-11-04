"""幾個算面積的小函式。"""
import math


def rect_area(w, h):
    return w * h


def circle_area(r):
    return math.pi * r * r


def square_area(a):
    return rect_area(a, a)
