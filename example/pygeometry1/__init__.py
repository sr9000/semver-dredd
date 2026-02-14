"""
PyGeometry is a simple python library about 2d primitives
"""

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5

def area(width, height):
    return width * height
