// Package gogeometry1 is a simple Go library about 2D primitives
package gogeometry1

import "math"

// Point represents a 2D point
type Point struct {
	X float64
	Y float64
}

// Distance calculates distance to another point
func (p *Point) Distance(other *Point) float64 {
	dx := p.X - other.X
	dy := p.Y - other.Y
	return math.Sqrt(dx*dx + dy*dy)
}

// Area calculates the area of a rectangle
func Area(width, height float64) float64 {
	return width * height
}
