// Package sub is a nested fixture package (included via "sub" import path).
package sub

// SubFunc is exported from the "sub" package.
func SubFunc() int {
	return 1
}
