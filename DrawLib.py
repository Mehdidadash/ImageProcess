from __future__ import annotations
import numpy as np
import pyvista as pv
import math
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize
import StandardDimentions as Stnds
import os.path

def create_CNC_code(FileType, stepsize, maxfeed, savefilename, IsReolix):
    
    data = Stnds.read_info(FileType)
    ESLH = Stnds.read_ESLH_values(FileType)
    
    Distances =  data['arrays']['Diameters'][:,0] 
    Diameters =  data['arrays']['Diameters'][:,1] 
    
    print("Number of ESLH files= ", int(len(ESLH)))
    
    for i in range(0,len(ESLH)):
        Diameters = Diameters - ESLH[i]
        
    L_min = min(Distances)
    L_max = max(Distances)
    n_points = int( (L_max-L_min)*100 )
    
    Pitch_info = data['arrays']['Pitchs']
    
    dia_spline = CubicSpline(Distances, Diameters)
    pitch_coefs = np.polyfit(Pitch_info[:,0], Pitch_info[:,1],1)
    theta_spline = find_theta_spline(L_min, L_max, pitch_coefs, n_points)
    
    n_point_based_on_stepsize =  int( (L_max-L_min)/stepsize )
    
    z = np.linspace(L_min, L_max, n_point_based_on_stepsize, endpoint=True)
    #z = np.arange(L_min, L_max + stepsize, stepsize)
    
    theta = theta_spline(z)

    feed = feed_function(z, maxfeed)
    
    print()
    
    with open(savefilename, "w") as file:
        
        first_line_text = "o<" + os.path.splitext(os.path.basename(savefilename))[0] + "> sub\n"

        
        reo = point_reo(L_max - z[0],dia_spline, theta_spline)
        xvalue = points_distance(0,0,reo[0],reo[1])
        
        if IsReolix: 
            avalue = solve_newton_raphson_singlePoint(L_max - z[0],dia_spline,theta_spline)
        else:
            avalue = 0
        
        dash7text = "#7=" + f"{xvalue:.5f}"  + "\n"
        dash9text = "#9=" + f"{avalue:.5f}"  + "\n"
        
        file.write(first_line_text)
        file.write(dash7text)
        file.write("#8=16\n")
        file.write(dash9text)
        
        for i in range(0, len(z)):
            
            reo = point_reo(L_max - z[i],dia_spline, theta_spline)
            
            xvalue = points_distance(0,0,reo[0],reo[1])
            zvalue = z[i]
            if IsReolix: 
                avalue = solve_newton_raphson_singlePoint(L_max - z[i],dia_spline,theta_spline)
            else:
                avalue = 0
            cvalue = (theta[len(z)-1] - theta[len(z)-i-1])*(180/3.1416)
            fvalue = feed[i]
            
            line = (
                f"g93 g01 x[{xvalue:.5f}*#2+#3] "
                f"z{zvalue:.5f} "
                f"a{avalue:.5f} "
                f"c{cvalue:.5f} "
                f"f[{fvalue:.5f}*#1]\n"
            )
            file.write(line)
            
            if i % 100 == 0:
                print(f"z{zvalue:.5f} ")
        
        file.write("o<fii_p08-25_01_v11> endsub")
        
    return True
            
def feed_function(z, feed_max):

    feed_func_values = np.zeros_like(z)
    
    for i in range(len(z)):
        i_percentage = (i / len(z)) * 100
        
        if i_percentage < 1:
            feed_func_values[i] = ((i_percentage * 90 + 10) * feed_max) / 100
        elif 1 <= i_percentage <= 95:
            feed_func_values[i] = (((i_percentage - 1) * (-70 / 89) + 100) * feed_max) / 100
        elif i_percentage > 95:
            feed_func_values[i] = (((i_percentage - 90) * (-20 / 10) + 30) * feed_max) / 100

    return feed_func_values
    
    
    
    
def Draw3D(FileType, section, drawHelix, SingleSurface):
    
    data = Stnds.read_info(FileType)
    
    Distances = data['arrays']['Diameters'][:,0]
    Diameters = data['arrays']['Diameters'][:,1]
    
    L_min = min(Distances)
    L_max = max(Distances)
    n_points = int( (L_max-L_min)*100 )
    
    Pitch_info = data['arrays']['Pitchs']
    
    dia_spline = CubicSpline(Distances, Diameters)
    pitch_coefs = np.polyfit(Pitch_info[:,0], Pitch_info[:,1],1)
    theta_spline = find_theta_spline(L_min, L_max, pitch_coefs, n_points)
    
    
    surface,helix = Draw(L_min, L_max, dia_spline, pitch_coefs, theta_spline, n_points, 100, section, drawHelix, SingleSurface)

    # F.solve(0,dia_spline, theta_spline)
    #solve_newton_raphson(0, 16, 160, dia_spline, theta_spline)

def triangle_circle_intersections(r, theta):
    """" This function assumes a circle of radius r at (0,0), then it 
    fits a equilateral triangle inside it so that a line from (0,0) to
    middle of first segment has a angle of theta and the segment is normal to 
    that line """
    
    d = r/2 #inside angles are 120, half of it is 60, cos(60)=1/2

    # Find coordinates of point A
    x_A = d * np.cos(theta)
    y_A = d * np.sin(theta)
    
    theta = theta%np.radians(360)
    
    # Determine slope of the line normal to the angle theta
    if theta == 0 or theta == np.radians(180):
        # Normal line is vertical (x = x_A)
        normal_slope = None
    else:
        normal_slope = -1 / np.tan(theta)  # Negative reciprocal of the slope

    # Circle equation: x^2 + y^2 = r^2
    # Normal line equation: y - y_A = normal_slope * (x - x_A)
    
    # If the normal line is vertical
    if normal_slope is None:
        # Intersection points at x = x_A
        if theta == 0:
            y_intersect1 = -np.sqrt(r**2 - x_A**2)
            y_intersect2 = -y_intersect1
        elif  theta == np.radians(180):
            y_intersect1 = np.sqrt(r**2 - x_A**2)
            y_intersect2 = -y_intersect1
        
        intersections1 = np.array([x_A, y_intersect1])
        intersections2 = np.array([x_A, y_intersect2])
        
    else:        
        # Coefficients for the quadratic equation
        A = 1 + normal_slope**2
        B = 2 * normal_slope * (y_A - normal_slope * x_A)
        C = (normal_slope**2)*x_A**2 - 2*normal_slope*x_A*y_A + (y_A**2 - r**2)

        # Find the discriminant
        discriminant = B**2 - 4*A*C
        
        if discriminant < 0:
            intersections1 = []  # No intersection
            intersections2 = []
        else:
            # Calculate the two intersection points
            x_intersect1 = (-B + np.sqrt(discriminant)) / (2 * A)
            x_intersect2 = (-B - np.sqrt(discriminant)) / (2 * A)

            # Calculate corresponding y values
            y_intersect1 = normal_slope * (x_intersect1 - x_A) + y_A
            y_intersect2 = normal_slope * (x_intersect2 - x_A) + y_A
            
            intersections1 = np.array([x_intersect1, y_intersect1])
            intersections2 = np.array([x_intersect2, y_intersect2])
            
            if(theta > np.radians(180)):
                intersections1,intersections2 = intersections2,intersections1
    intersection3 = rotate_point(intersections2,120)
    return intersections1,intersections2,intersection3

def rotate_point(point, angle_degrees):
    """Rotate a point (x, y) around the origin by a given angle in degrees."""
    angle_radians = np.radians(angle_degrees)
    rotation_matrix = np.array([
        [np.cos(angle_radians), -np.sin(angle_radians)],
        [np.sin(angle_radians), np.cos(angle_radians)]
    ])
    return np.dot(rotation_matrix, point)


def line_points(A, B, n):
    
    """ Distributes n points along the line AB, including points A, B
    Returns a (n+1, 2) array of coordinates."""
    
    # Create n points along line AB, including A
    points_AB = np.linspace(A, B, n+1, endpoint=False)
    
    # Concatenate the points into a single array
    final_points = np.vstack((points_AB))
    
    return final_points

def distribute_points_line(A, B, C, n):
    
    """ Distributes n points along the lines AB, BC, and CA, including points A, B, and C only once.
    Returns a (3n+3, 2) array of coordinates."""
    
    # Create n points along line AB, including A
    points_AB = line_points(A, B, n)
    
    # Create n points along line BC, including B
    points_BC = line_points(B, C, n)
    
    # Create n points along line CA, including C
    points_CA = line_points(C, A, n)
    
    # Concatenate the points into a single array
    final_points = np.vstack((points_AB, points_BC, points_CA))
    
    return final_points


def arc_points(start, end, center, n):
    """Calculate points on an arc from start to end with a given center."""
    # Calculate angles for start and end points
    angle_start = np.arctan2(start[1] - center[1], start[0] - center[0])
    angle_end = np.arctan2(end[1] - center[1], end[0] - center[0])
    
    # Normalize angles to be in the range [0, 2*pi)
    angle_start = angle_start % (2 * np.pi)
    angle_end = angle_end % (2 * np.pi)
    
    # Ensure we go the short way around the circle
    if angle_end < angle_start:
        angle_end += 2 * np.pi
        
    # Create an array of angles for the distributed points
    angles = np.linspace(angle_start, angle_end, n, endpoint=False)
    
    # Calculate the radius from center to start point
    radius = np.sqrt((start[0] - center[0])**2 + (start[1] - center[1])**2)
    
    # Calculate the coordinates of the points on the arc
    points = np.array([(center[0] + radius * np.cos(angle), 
                        center[1] + radius * np.sin(angle)) for angle in angles])
    
    return points

def distribute_points_arc(A, B, C, n):
    # Generate points for each arc
    arc_AB = arc_points(A, B, C, n)  # Arc from A to B with center C
    arc_BC = arc_points(B, C, A, n)  # Arc from B to C with center A
    arc_CA = arc_points(C, A, B, n)  # Arc from C to A with center B
    
    # Combine all points into a single array
    all_points = np.vstack((arc_AB, arc_BC, arc_CA))
    
    return all_points

def points_distance(x1,y1,x2,y2):
    d = math.sqrt((x2-x1)**2+(y2-y1)**2)
    return d


def find_theta_spline(zMin, zMax, PitchCoefs, num_points_z):
    z = np.linspace(zMin, zMax, num_points_z,endpoint=True)
    
    theta = np.zeros_like(z)
    
    Pitch = np.polyval(PitchCoefs,z)
    
    # Calculate theta by integrating the inverse of the pitch over z
    for i in range(0, len(z)):
        
        if i==0:
            dz=0
            theta[i] = 0
        else:
            dz = z[i] - z[i-1]
            theta[i] = theta[i-1] + (2 * np.pi / Pitch[i]) * dz
    
    spline = CubicSpline(z, theta)
    
    return spline

def Draw(zMin, zMax, dia_spline, PitchCoefs, theta_spline, num_points_z, num_points_section, section, drawHelix, SingleSurface):
    z = np.linspace(zMin, zMax, num_points_z,endpoint=True)
    
    theta = theta_spline(z)
    theta_helix = theta + np.radians(60)
    
    Pitch = np.polyval(PitchCoefs,z)
    Dia = dia_spline(z)
    
    SurfacePoints = []
    
    # Calculate theta by integrating the inverse of the pitch over z
    for i in range(0, len(z)):
        
        A,B,C = triangle_circle_intersections(Dia[i]/2, theta[i])
        
        if section == 'reolix':
            if SingleSurface:
                XYpoints = arc_points(A,B,C,num_points_section)
            else:
                XYpoints = distribute_points_arc(A,B,C,num_points_section)
        else:
            if SingleSurface:
                XYpoints = line_points(A,B,num_points_section)
            else:
                XYpoints = distribute_points_line(A,B,C,num_points_section)
        
        z_array = np.full((XYpoints.shape[0], 1), z[i])
        SurfacePoints.append(np.hstack((XYpoints, z_array)))
        
    SurfacePoints = np.vstack(SurfacePoints)
    point_cloud = pv.PolyData(SurfacePoints)
    #point_cloud = point_cloud.rotate_x(180)
    
    x = 0.5 * Dia * np.cos(theta_helix)
    y = 0.5 * Dia * np.sin(theta_helix)
    
    helix_points = np.vstack((x, y, z)).T
    helix = pv.PolyData(helix_points)
    #helix = helix.rotate_x(180)

    plotter = pv.Plotter()
    plotter.add_mesh(point_cloud, color="maroon", point_size=5.0, render_points_as_spheres=True)
    
    if drawHelix:
        if SingleSurface:
            helix2 = helix.rotate_z(-120)
            plotter.add_mesh(helix, color='cyan', line_width=10, render_points_as_spheres=True)
            plotter.add_mesh(helix2, color='cyan', line_width=10, render_points_as_spheres=True)
        else:
            helix2 = helix.rotate_z(-120)
            helix3 = helix.rotate_z(120)
            plotter.add_mesh(helix, color='cyan', line_width=10, render_points_as_spheres=True)
            plotter.add_mesh(helix2, color='cyan', line_width=10, render_points_as_spheres=True)
            plotter.add_mesh(helix3, color='cyan', line_width=10, render_points_as_spheres=True)
            
#==========================================================================
#                               For Test
#==========================================================================
    # z_test = 7
    # reo = point_reo(z_test,dia_spline, theta_spline)
    # z_a0 = z_test + 0.2
    # z_b0 = z_test - 0.2
    
    # z_a0, z_b0 = newton_raphson(z_a0, z_b0, reo, dia_spline, theta_spline, tol=1e-6, max_iter=100)
    
    # PA = point_A(z_a0, dia_spline, theta_spline)
    # PB = point_B(z_b0, dia_spline, theta_spline)
    
    # AB_Line = pv.Line(pointa=PA, pointb=PB)
    # plotter.add_mesh(AB_Line, color='magenta', line_width=10)
#==========================================================================
#==========================================================================


    ZeroPlane = pv.Plane(center=(0,0,zMin),direction=(0,0,1),i_size=1,j_size=1)
    EndPlane = pv.Plane(center=(0,0,zMax),direction=(0,0,1),i_size=2,j_size=2)
    
    XAxis = pv.Line(pointa=(0, 0, 0), pointb=(3, 0, 0))
    YAxis = pv.Line(pointa=(0, 0, 0), pointb=(0, 3, 0))
    ZAxis = pv.Line(pointa=(0, 0, zMax+0.1*zMax), pointb=(0, 0,-1))
    XAxis_text = pv.Text3D('X', center = (3, 0, 0), normal=(1,0,0), depth=0.1, width=1)
    YAxis_text = pv.Text3D('y', center = (0, 3, 0), normal=(0,1,0), depth=0.1, width=1)
    ZAxis_text = pv.Text3D('z', center = (0, 0, zMax+0.1*zMax), normal=(0,0,1), depth=0.1, width=1)
    plotter.add_mesh(XAxis, color='green', line_width=1)
    plotter.add_mesh(YAxis, color='green', line_width=1)
    plotter.add_mesh(ZAxis, color='green', line_width=1)

    plotter.add_mesh(ZeroPlane,color='midnightblue',opacity=0.2)
    plotter.add_mesh(EndPlane,color='midnightblue',opacity=0.2)

    plotter.add_mesh(XAxis_text, color='green')
    plotter.add_mesh(YAxis_text, color='green')
    plotter.add_mesh(ZAxis_text, color='green')
    plotter.camera.SetParallelProjection(True)
    
    minPoint = zMax+zMin/2
    
    plotter.camera.position = (-25, -25, -minPoint)
    plotter.camera.focal_point = (0, 0, 0)
    plotter.camera.up = (0.0, -1.0, 0.0)
    
    plotter.add_measurement_widget(color = "gold")
    
    plotter.show()
    
    return(SurfacePoints,helix_points)

def point_A(z, dia_spline, theta_spline):
    
    theta = theta_spline(z)
    Dia = dia_spline(z)
    A,B,C = triangle_circle_intersections(Dia/2, theta)

    return np.array([A[0],A[1],z]).T

def point_B(z, dia_spline, theta_spline):
    
    theta = theta_spline(z)
    Dia = dia_spline(z)
    A,B,C = triangle_circle_intersections(Dia/2, theta)

    return np.array([B[0],B[1],z]).T

def point_reo(z,dia_spline, theta_spline):

    theta = theta_spline(z)
    dia = dia_spline(z)
    A,B,C = triangle_circle_intersections(dia/2,theta)

    reolixDia = points_distance(A[0],A[1],C[0],C[1])
    M = [(A[0]+B[0])/2,(A[1]+B[1])/2]
    CM = [M[0]-C[0],M[1]-C[1]]
    CM_hat = CM / np.linalg.norm(CM)
    x_reo = C[0] + reolixDia* CM_hat[0]
    y_reo = C[1] + reolixDia* CM_hat[1]
    return np.array([x_reo,y_reo,z]).T

def collinearity_condition(z_a, z_b, reo, dia_spline, theta_spline):
    # Compute Point A and Point B for the given z
    PA = point_A(z_a, dia_spline, theta_spline)
    PB = point_B(z_b, dia_spline, theta_spline)
    
    # Direction vectors from reo to PA and PB
    v1 = PA - reo
    v2 = PB - reo
    
    # Cross product of the vectors v1 and v2
    cross_product = np.cross(v1, v2)
    
    # The condition for collinearity is that the cross product is (0,0,0)
    return np.linalg.norm(cross_product)

def coplanarity_condition(z_a, z_b, reo, dia_spline, theta_spline):
    # Create vectors
    P1 = point_A(z_a, dia_spline, theta_spline)
    P2 = point_B(z_b, dia_spline, theta_spline)
    P3 = reo
    P4 = np.array([[0, 0, 0]])
    
    v1 = np.array(P2) - np.array(P1)
    v2 = np.array(P3) - np.array(P1)
    v3 = np.array(P4) - np.array(P1)
    
    # Compute the scalar triple product (determinant)
    matrix = np.vstack([v1, v2, v3])
    det = np.linalg.det(matrix)
    
    return det

def jacobian(z_a, z_b, reo, dia_spline, theta_spline):
    h = 1e-7  # Small step for numerical differentiation
    
    
    f1_x1_p = collinearity_condition(z_a + h, z_b, reo, dia_spline, theta_spline)
    f1_x1_n = collinearity_condition(z_a - h, z_b, reo, dia_spline, theta_spline)
    df1_dx1 = (f1_x1_p - f1_x1_n) / (2 * h)
    
    f1_x2_p = collinearity_condition(z_a, z_b + h, reo, dia_spline, theta_spline)
    f1_x2_n = collinearity_condition(z_a, z_b - h, reo, dia_spline, theta_spline)
    df1_dx2 = (f1_x2_p - f1_x2_n) / (2 * h)
    
    f2_x1_p = coplanarity_condition(z_a + h, z_b, reo, dia_spline, theta_spline)
    f2_x1_n = coplanarity_condition(z_a - h, z_b, reo, dia_spline, theta_spline)
    df2_dx1 = (f2_x1_p - f2_x1_n) / (2 * h)
    
    f2_x2_p = coplanarity_condition(z_a, z_b + h, reo, dia_spline, theta_spline)
    f2_x2_n = coplanarity_condition(z_a, z_b - h, reo, dia_spline, theta_spline)
    df2_dx2 = (f2_x2_p - f2_x2_n) / (2 * h)
    
    # Return the Jacobian as a 2x2 matrix
    return np.array([[df1_dx1, df1_dx2], [df2_dx1, df2_dx2]])

def newton_raphson(z_a0, z_b0, reo, dia_spline, theta_spline, tol=1e-6, max_iter=100):
    z_a, z_b = z_a0, z_b0  # Initial guesses

    for i in range(max_iter):
        # Compute collinearity conditions
        f1_x = collinearity_condition(z_a, z_b, reo, dia_spline, theta_spline)
        f2_x = coplanarity_condition(z_a, z_b, reo, dia_spline, theta_spline)
        f_x = np.array([f1_x,f2_x])
        # Compute Jacobian matrix
        jacobian_matrix = jacobian(z_a, z_b, reo, dia_spline, theta_spline)
        
        # Solve J * delta_z = -f
        delta_z = np.linalg.solve(jacobian_matrix, -f_x)
        
        # Update z_a and z_b
        z_a += 0.7*delta_z[0]
        z_b += 0.7*delta_z[1]
        
        delta_z_norm = np.linalg.norm(delta_z)
        
        # Check for convergence
        if delta_z_norm < tol:
            #print(f"Converged in {i+1} iterations")
            return z_a, z_b
    
    raise Exception("Newton-Raphson did not converge")
    
def solve_newton_raphson(z_min , z_max , z_num, dia_spline, theta_spline):
    
    z_ = np.linspace(z_min, z_max, z_num, endpoint=True)
    
    z_a0 = z_[0] + 0.2
    z_b0 = z_[0] - 0.2
    
    for i in range(0,len(z_)):
        z = z_[i]
        reo = point_reo(z,dia_spline, theta_spline)
        z_a0, z_b0 = newton_raphson(z_a0, z_b0, reo, dia_spline, theta_spline, tol=1e-6, max_iter=100)
        
        PA = point_A(z_a0, dia_spline, theta_spline)
        PB = point_B(z_b0, dia_spline, theta_spline)
      
        #angle_relative_to_z_axis(PB,PA)
        
        #print("--------- z= ", z)
        print(angle_relative_to_z_axis(PB,PA))
        #print(z_a0, z_b0)
        #print(' ')
        
def solve_newton_raphson_singlePoint_OLD(z_point, dia_spline, theta_spline):
    
    z_a0 = z_point + 0.05
    z_b0 = z_point - 0.05
    

    reo = point_reo(z_point,dia_spline, theta_spline)
    z_a0, z_b0 = newton_raphson(z_a0, z_b0, reo, dia_spline, theta_spline, tol=1e-6, max_iter=100)
        
    PA = point_A(z_a0, dia_spline, theta_spline)
    PB = point_B(z_b0, dia_spline, theta_spline)
      

    return (angle_relative_to_z_axis(PB,PA))

def solve_newton_raphson_singlePoint(z_point, dia_spline, theta_spline):
    
    offset_step = 0.05
    retries = 0

    offset = offset_step
    max_retries = 4
    
    while retries < max_retries:
        z_a0 = z_point + offset
        z_b0 = z_point - offset

        reo = point_reo(z_point, dia_spline, theta_spline)

        try:
            # Try solving with the current offsets
            z_a0, z_b0 = newton_raphson(z_a0, z_b0, reo, dia_spline, theta_spline, tol=1e-6, max_iter=100)
            
            # If successful, calculate points and angle
            PA = point_A(z_a0, dia_spline, theta_spline)
            PB = point_B(z_b0, dia_spline, theta_spline)

            return angle_relative_to_z_axis(PB, PA)
        except Exception as e:
            # If it fails, adjust offsets and retry
            retries += 1
            offset += offset_step
            #print(f"Retry {retries}/{max_retries}: Adjusting offsets to {offset:.4f}")

    # If all retries fail, raise an exception
    raise ValueError(f"Newton-Raphson method failed to converge after {max_retries} retries with adjusted offsets.")
    
def collinearity_condition_minimize(z, reo, dia_spline, theta_spline, z_limit):
    z_a, z_b = z

    # Ensure the constraints: z_a > z_limit and z_b < z_limit
    if z_a <= z_limit or z_b >= z_limit:
        return np.inf  # Return a large value if constraints are violated
    
    # Compute the cross product value (the objective to minimize)
    cross_product_value = collinearity_condition(z_a, z_b, reo, dia_spline, theta_spline)
    
    return cross_product_value


def solve(z,dia_spline, theta_spline):
   reo = point_reo(z,dia_spline, theta_spline)
    
   # Initial guess for z_a and z_b ( might need to adjust based on problem)
   z_limit=z
   initial_guess = [z_limit + 0.2, z_limit - 0.2]

   # Call the minimize function with bounds to enforce z_a > z_limit and z_b < z_limit
   result = minimize(
       collinearity_condition_minimize,
       initial_guess,
       args=(reo, dia_spline, theta_spline, z_limit),
       bounds=[(z_limit, None), (None, z_limit)],  # Bounds for z_a and z_b
       tol=1e-9,  # Set a very small tolerance for high accuracy
        options={
                'maxiter': 2000,  # Increase the number of iterations
                'disp': False,     # Display output for diagnostics
                'ftol': 1e-9      # Function tolerance for stopping criteria
                }
       )
   
   # Extract optimized z_a and z_b
   z_a_opt, z_b_opt = result.x

   # Check if optimization was successful
   if result.success:
       return z_a_opt, z_b_opt
   else:
       print("Optimization failed.")
       return 0, 0


def angle_relative_to_z_axis(point_N, point_M):
    """" this function calculates the angle of a line from M to N relative to Z+ """
    x_n, y_n, z_n = point_N
    x_m, y_m, z_m = point_M

    # Calculate the direction vector from N to M
    v = np.array([x_m - x_n, y_m - y_n, z_m - z_n])

    # Calculate the magnitude of the vector
    magnitude_v = np.linalg.norm(v)

    # Get the z-component of the vector
    v_z = v[2]

    # Calculate the angle in radians
    cos_theta = v_z / magnitude_v
    theta_radians = np.arccos(cos_theta)

    # Convert to degrees
    theta_degrees = np.degrees(theta_radians)

    return theta_degrees


def solve_a_angle(z,dia_spline,theta_spline):
    reo = point_reo(z, dia_spline, theta_spline)
    
    z_a ,z_b = solve(z,dia_spline, theta_spline)
    
    PA = point_A(z_a, dia_spline, theta_spline)
    PB = point_B(z_b, dia_spline, theta_spline)

    v1 = PA - reo
    v2 = PB - reo
    
    # Cross product of the vectors v1 and v2
    cross_product = np.cross(v1, v2)
    
    return np.linalg.norm(cross_product), angle_relative_to_z_axis(PB,PA)




