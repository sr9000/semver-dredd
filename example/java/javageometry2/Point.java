/**
 * JavaGeometry is a simple Java library about 2D and 3D primitives
 */
public class Point {
    public double x;
    public double y;
    public double z;

    public Point(double x, double y) {
        this(x, y, 0);
    }

    public Point(double x, double y, double z) {
        this.x = x;
        this.y = y;
        this.z = z;
    }

    public double distance(Point other) {
        double dx = this.x - other.x;
        double dy = this.y - other.y;
        double dz = this.z - other.z;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    public void translate(double dx, double dy, double dz) {
        this.x += dx;
        this.y += dy;
        this.z += dz;
    }
}
