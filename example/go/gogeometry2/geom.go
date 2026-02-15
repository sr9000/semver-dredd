// Package gogeometry2 is a simple Go library about 2D and 3D primitives
package gogeometry2

import "math"

// Point represents a 3D point (extended from 2D)
type Point struct {
	X float64
	Y float64
	Z float64
}

// Distance calculates distance to another point
func (p *Point) Distance(other *Point) float64 {
	dx := p.X - other.X
	dy := p.Y - other.Y
	dz := p.Z - other.Z
	return math.Sqrt(dx*dx + dy*dy + dz*dz)
}

// Translate moves the point by given deltas
func (p *Point) Translate(dx, dy, dz float64) {
	p.X += dx
	p.Y += dy
	p.Z += dz
}

// Area calculates the area of a rectangle
func Area(width, height float64) float64 {
	return width * height
}

// Volume calculates the volume of a rectangular prism
func Volume(width, height, depth float64) float64 {
	return width * height * depth
}
