// Package internal is nested under sub, used to test the exclude "*" rule.
package internal

// InternalFunc is exported from "sub/internal".
func InternalFunc() int {
	return 2
}
