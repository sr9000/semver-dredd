"""
PyGeometry is a simple python library about 2d primitives
"""

class Point:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z

    def distance(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)**0.5

    def translate(self, dx, dy, dz=0):
        self.x += dx
        self.y += dy
        self.z += dz

def area(width, height):
    return width * height

def volume(width, height, depth):
    return width * height * depth
