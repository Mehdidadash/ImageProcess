import cv2
import os
import math
import sys
import csv
import numpy as np
from scipy.signal import savgol_filter
from scipy.signal import find_peaks
from scipy.interpolate import CubicSpline
from sklearn.metrics import r2_score
from scipy.optimize import fsolve
import matplotlib.pyplot as plt
import rawpy
import imageio
import StandardDimentions as Stnds 

def MAIN(input_directory):
    
    results = CalculateAllImages(input_directory)

    # Path to the StandardDimentions folder
    base_dir = "StandardDimentions"
    data = {}
    for folder_name in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder_name)
        if os.path.isdir(folder_path):  # Ensure it's a folder
            try:
                data[folder_name] = Stnds.read_info(folder_name, base_dir)
            except FileNotFoundError as e:
                print(f"Error reading folder '{folder_name}': {e}")

    # Collect measured diameters from all images
    all_measured_diameters = []
    for result in results:
        measured_diameters = result["MeasuredDs"][1]  # Extract measured diameters
        all_measured_diameters.append(measured_diameters)

    # Convert to a NumPy array for easier averaging
    all_measured_diameters = np.array(all_measured_diameters)

    # Calculate the average diameter across all images
    average_diameters = np.mean(all_measured_diameters, axis=0)

    # Save raw average diameters to raw.txt
    raw_output_path = os.path.join(input_directory, "raw.txt")
    with open(raw_output_path, "w") as raw_file:
        for value in average_diameters:
            raw_file.write(f"{value:.3f}\n")
        # --- Write results to CSV in main folder ---
    main_folder = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(main_folder, "all_raw_results.csv")
    folder_name = os.path.basename(os.path.normpath(input_directory))
    new_column = [folder_name] + [f"{value:.3f}" for value in average_diameters]

    if os.path.exists(csv_path):
        # Read existing CSV
        with open(csv_path, "r", newline="") as csvfile:
            reader = list(csv.reader(csvfile))
        # Pad rows if needed
        max_len = max(len(reader), len(new_column))
        while len(reader) < max_len:
            reader.append([""] * len(reader[0]))
        while len(new_column) < max_len:
            new_column.append("")
        # Append new column
        for i, val in enumerate(new_column):
            reader[i].append(val)
        # Write back
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(reader)
    else:
        # Create new CSV with this column
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            for val in new_column:
                writer.writerow([val])
    # --- End CSV logic ---
    # Compare the average diameters with the corresponding diameters in the data
    closest_filetype = None
    smallest_difference = float("inf")
    comparison_results = {}


    for file_type, file_data in data.items():
        standard_distances = file_data["arrays"]["Diameters"][:, 0]  # Distances
        standard_diameters = file_data["arrays"]["Diameters"][:, 1]  # Diameters

        # Only use indices 0,1,2,3,4,10 for closest type comparison
        compare_indices = [0, 1, 2, 3, 4]
        compare_indices = [i for i in compare_indices if i < len(standard_distances) and i < len(average_diameters)]

        # For closest type: use only selected indices
        diameter_comparison_selected = average_diameters[compare_indices] - standard_diameters[compare_indices]
        total_difference = np.sum(np.abs(diameter_comparison_selected))

        # For output: use all points
        distance_comparison_all = standard_distances[:min(len(standard_distances), len(average_diameters))]
        diameter_comparison_all = average_diameters[:min(len(standard_diameters), len(average_diameters))] - standard_diameters[:min(len(standard_diameters), len(average_diameters))]

        comparison_results[file_type] = {
            "distances": distance_comparison_all,
            "diameter_differences": diameter_comparison_all,
            "total_difference": total_difference,
        }

        if total_difference < smallest_difference:
            smallest_difference = total_difference
            closest_filetype = file_type

    # Write the differences for all points to a text file
    output_file_path = os.path.join(input_directory, f"{closest_filetype}_diff.txt")
    with open(output_file_path, "w") as file:
        for distance, difference in zip(
            comparison_results[closest_filetype]["distances"],
            comparison_results[closest_filetype]["diameter_differences"],
        ):
            file.write(f"{difference:.3f}\n")

    print(f"Diameter differences written to: {output_file_path}")

    # Plot standard diameters and average diameters
    plt.figure(figsize=(10, 6))
    for file_type, file_data in data.items():
        standard_distances = file_data["arrays"]["Diameters"][:, 0]  # Distances
        standard_diameters = file_data["arrays"]["Diameters"][:, 1]  # Diameters

        # Plot standard diameters for this FileType
        plt.plot(standard_distances, standard_diameters, label=f"{file_type} Standard Diameters", marker="o")

    # Plot average diameters
    plt.plot(np.arange(len(average_diameters)), average_diameters, label="Average Diameters", color="black", linestyle="--", marker="*")

    # Add labels, legend, and grid
    plt.title(f"Closest FileType: {closest_filetype}", fontsize=12, color="red", transform=plt.gca().transAxes, ha="center")
    plt.xlabel("Distances (mm)")
    plt.ylabel("Diameters (mm)")
    plt.legend()
    plt.grid(True)
    
    plot_output_path = os.path.join(input_directory, f"{closest_filetype}_comparison_plot.png")
    plt.savefig(plot_output_path, dpi=300, bbox_inches="tight")  # Save the plot with high resolution
    plt.close()  # Close the plot to free memory

    return plot_output_path, closest_filetype
    

def CalculateAllImages(input_directory):
    
    TopGaugeSize = 19.674
    BottomGaugeSize = 10.381
    RightGaugeSize = 7.608
    
    # Path to the StandardDimentions folder
    base_dir = "StandardDimentions"

    # Read all subfolders in the StandardDimentions folder



    bmp_files = checkFolder(input_directory)
            
    results = []

    for ImagePath in bmp_files:
        image_name = os.path.splitext(os.path.basename(ImagePath))[0]
        PixelSize,VerticalScale,Threshold,LaseError = CalibrateImage(ImagePath,TopGaugeSize,BottomGaugeSize,RightGaugeSize)
    
        file_x, file_y,_ = FindContour(ImagePath,Threshold)
        y_smooth = ReduceYNoise(file_x, file_y)
        y_CenterLine,coefficients = FitCenterLine(file_x,y_smooth)
        theta_degrees, x_TipLong, y_TipLong, x_TipShort, y_TipShort = TipInformation(file_x, y_smooth)
        Tip = [x_TipLong, y_TipLong, x_TipShort, y_TipShort]
    
        Standard_Distances = np.arange(0, 17, 1)
        MeasuredDs = CalDias(Standard_Distances, file_x, file_y, PixelSize, VerticalScale)
        results.append({"image_name": image_name, "MeasuredDs": MeasuredDs})
        plot_image_with_data(ImagePath, file_x, file_y, MeasuredDs)

    return results

def plot_image_with_data(ImagePath, file_x, file_y, MeasuredDs):

    CenterPoints = MeasuredDs[0]
    Intersection_U = MeasuredDs[4]
    Intersection_D = MeasuredDs[5]
    xMax, yMax = MeasuredDs[6][:, 0], MeasuredDs[6][:, 1]
    xMin, yMin = MeasuredDs[7][:, 0], MeasuredDs[7][:, 1]

    # Read and display the image
    ImageCopy = cv2.imread(ImagePath)  # Read the image
    plt.figure(figsize=(10, 6))
    plt.imshow(cv2.cvtColor(ImageCopy, cv2.COLOR_BGR2RGB))  # Convert BGR to RGB for Matplotlib

    # Plot the contour
    plt.plot(file_x, file_y, label="Contour", color="blue", linewidth=1)

    # Plot the center points
    CenterPoints = np.array(CenterPoints)
    plt.scatter(CenterPoints[:, 0], CenterPoints[:, 1], color="red", label="Center Points", s=5, zorder=5)

    # Plot the intersections
    Intersection_U = np.array(Intersection_U)
    Intersection_D = np.array(Intersection_D)
    plt.scatter(Intersection_U[:, 0], Intersection_U[:, 1], color="green", label="Intersection U", s=5, zorder=5)
    plt.scatter(Intersection_D[:, 0], Intersection_D[:, 1], color="orange", label="Intersection D", s=5, zorder=5)

    # Plot the maxima and minima
    plt.scatter(xMax, yMax, color="purple", label="Maxima", marker="*", s=5, zorder=5)
    plt.scatter(xMin, yMin, color="cyan", label="Minima", marker="*", s=5, zorder=5)

    # Add labels and legend
    plt.title(f"Image: {os.path.basename(ImagePath)}")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.gca().invert_yaxis()  # Invert y-axis for image coordinates

    # Save the plot
    output_path = os.path.splitext(ImagePath)[0] + "_measured.png"  # Add "_measured" suffix
    plt.savefig(output_path, dpi=300, bbox_inches="tight")  # Save the plot with high resolution
    plt.close()  # Close the plot to free memory

def ShowDeltas(Deltas):
    NumberOfImages = len(Deltas)
    NumberOfDistances = len(Deltas[0][1])
    ImageNames = []
    ImageDelta = []
    ImageDistances = []
    
    TopString = 'L\t\t\t'
    for i in range(NumberOfImages):
        ImageNames.append(Deltas[i][0])
        ImageDelta.append(Deltas[i][2])
        TopString = TopString + Deltas[i][0] + '\t\t'
        
    if NumberOfImages>1 :
        TopString = TopString + "Avrg"
        
    SecondLine = '-' * len(TopString)
    ImageDelta = np.array(ImageDelta)
    DeltaAverages = np.mean(ImageDelta, axis=0)
    
    Lines = []
    for j in range(NumberOfDistances):
        ImageDistances.append(Deltas[0][1][j])
        LineString = ""
        LineString = LineString + str(Deltas[0][1][j]) + "\t\t\t"
        
        for i in range(NumberOfImages):
            LineString = LineString + "{:.3f}".format(Deltas[i][2][j]) + "\t\t"
            
        if NumberOfImages>1 :
            LineString = LineString + "{:.3f}".format(DeltaAverages[j]) + "\t\t"
        Lines.append(LineString)


    print("\n")
    print("**************************************************************")         
    print(TopString)
    print(SecondLine)
    for j in range(NumberOfDistances):
        print(Lines[j])
    
    
    for i in range(NumberOfImages):
        plt.plot(ImageDistances,ImageDelta[i],label=ImageNames[i], alpha=.4)
    
    if NumberOfImages>1 :
        plt.plot(ImageDistances,DeltaAverages,label='Average',color='black',linestyle='--')
    plt.xticks(ImageDistances)    
    plt.legend()
    plt.grid(axis='x', color='0.95')
    plt.grid(axis='y', color='0.95')
    plt.xlabel('distances(mm)')
    plt.ylabel('Error (mm)')
    plt.axhline(0,linewidth=1, color='black',alpha=.3)
    plt.show()
    
def checkFolder(input_directory):
    if not os.path.exists(input_directory):
        print("Directory does not exist")
        sys.exit()
    else:
        if len(os.listdir(input_directory)) == 0:
            print("Directory is empty")
            sys.exit()

    bmp_files = [os.path.join(input_directory,filename) for filename in os.listdir(input_directory) if (filename.lower().endswith('.bmp') )]
    return bmp_files

def CalDias(Standard_Distances, file_x, file_y, PixelSize, VerticalScale):

    Standard_Distances = np.arange(0, 17, 1)

    #Smooth the y values to reduce noise
    y_smooth = ReduceYNoise(file_x, file_y)

    #fit a center line through x and y points
    y_CenterLine,coefficients = FitCenterLine(file_x,y_smooth)

    #find the information of tip
    theta_degrees, x_TipLong, y_TipLong, x_TipShort, y_TipShort = TipInformation(file_x, y_smooth)
    TipPixels,TipDiameter = CalculateTipDiameter(file_x,y_smooth,x_TipShort,y_TipShort,PixelSize)
    
    xMax, yMax, xMin, yMin = FindLocalMaxMin(file_x, y_smooth,y_CenterLine,PixelSize)
    
    leng = len(Standard_Distances)
    
    Measured_Diameters = []
    Measured_Diameters_U = []
    Measured_Diameters_D = []
    Intersection_U = []
    Intersection_D = []
    CenterPoints = []
    
    # Tip
    x_tip_index = np.argmax(file_x)
    y_tip_index = np.argmax(file_x)       
    x_tip = file_x[x_tip_index]
    y_tip = y_CenterLine[y_tip_index]
    
    D_tip_NewMethod, IntersectMax_NewMethod, IntersectMin_NewMethod = CalTipDiaFromMinMaxPoints(file_x, file_y, PixelSize, VerticalScale)
    
    Measured_Diameters.append(D_tip_NewMethod)
    Measured_Diameters_U.append(D_tip_NewMethod/2)
    Measured_Diameters_D.append(D_tip_NewMethod/2)
    
    Intersection_U.append([IntersectMax_NewMethod[0], IntersectMax_NewMethod[1]])
    Intersection_D.append([IntersectMin_NewMethod[0], IntersectMin_NewMethod[1]])
    
    TipPointOnCenterLine = find_normal_point(coefficients,[IntersectMax_NewMethod[0], IntersectMax_NewMethod[1]])
    CenterPoints.append(TipPointOnCenterLine)
    
    for i in range(1,leng):
        
        DistanceFromTip = Standard_Distances[i]

        XnCenter,YnCenter = XnY_OnCenterLine(x_tip, y_tip, y_CenterLine, coefficients, DistanceFromTip, PixelSize)
        
        find_UpperLowerPoints(xMax, yMax, XnCenter, YnCenter, coefficients[0], coefficients[1])
        
        lower_point_Max,upper_point_Max = find_UpperLowerPoints(xMax, yMax, XnCenter, YnCenter, coefficients[0], coefficients[1])
        lower_point_Min,upper_point_Min = find_UpperLowerPoints(xMin, yMin, XnCenter, YnCenter, coefficients[0], coefficients[1])
        
        if lower_point_Max is not None and upper_point_Max is not None:       
            #D_Max, Intersection_Max = distance_and_intersection(lower_point_Max,upper_point_Max,[XnCenter,YnCenter])
            D_Max, Intersection_Max = distance_and_intersection_N(lower_point_Max,upper_point_Max,[XnCenter,YnCenter],coefficients[0],coefficients[1])
        else:

            D_Max = np.nan
            Intersection_Max = np.nan
            
            
        if lower_point_Min is not None and upper_point_Min is not None:
            #D_Min, Intersection_Min = distance_and_intersection(lower_point_Min,upper_point_Min,[XnCenter,YnCenter])
            D_Min, Intersection_Min = distance_and_intersection_N(lower_point_Min,upper_point_Min,[XnCenter,YnCenter],coefficients[0],coefficients[1])
        else:
            D_Min = np.nan
            Intersection_Min = np.nan
        
        CenterPoints.append([XnCenter,YnCenter])

        D_Max = (D_Max)*(PixelSize/1000)*VerticalScale
        D_Min = (D_Min)*(PixelSize/1000)*VerticalScale
        
        Measured_Diameters.append(D_Max+D_Min)
        Measured_Diameters_U.append(D_Max)
        Measured_Diameters_D.append(D_Min)
        
        Intersection_U.append(Intersection_Max)
        Intersection_D.append(Intersection_Min)
        
        
    Results = [] 
    
    Results.append(CenterPoints)                        # 0
    Results.append(Measured_Diameters)                  # 1
    Results.append(Measured_Diameters_U)                # 2
    Results.append(Measured_Diameters_D)                # 3
    Results.append(Intersection_U)                      # 4
    Results.append(Intersection_D)                      # 5
    Results.append(np.column_stack((xMax, yMax)))       # 6
    Results.append(np.column_stack((xMin, yMin)))       # 7
    
    return Results
    
def PrintResults(ImagePath, theta_degrees, Standard_Distances, Standard_Diameters, Measured_Diameters, BestThreshold, LastError, VerticalScaling):
    
    print("\n")
    print("**************************************************************") 
    print("\t\t\t\t\t\t",os.path.basename(ImagePath))
    print("**************************************************************") 
    print("Best value for threshold is: ",BestThreshold,"\t","with Error : ","{:.2f}".format(LastError)," microns")
    # print("For the best threshold, vertical error is: ","{:.2f}".format(VError)," microns")
    # print("Pixel size is: ","{:.3f}".format(PixelSize)," microns")
    # print("Wire Diameter is: ","{:.3f}".format(WireDiameter)," milimeters")
    print("Vertical scaling for wire is:", "{:.3f}".format(VerticalScaling))
    print("===============================")  
    
    
    print("Tip angle is: ","{:.1f}".format(theta_degrees)," degrees")
    print("===============================")  
    
    print('L\t','ISO\t','Part\t','Error\t(mm)')
    print('-------------------------------')
    for i in range(len(Measured_Diameters)):
        delta = Measured_Diameters[i]-Standard_Diameters[i]
        print(Standard_Distances[i],'\t',Standard_Diameters[i],'\t','%.3f'%Measured_Diameters[i],'\t','%.3f'%delta)
            
def PlotResults(ImagePath, file_x, file_y,Tip, Results, PixelSize, VerticalScale):
    
    ImageCopy = cv2.imread(ImagePath) #make a copy of the original image
    plt.figure(figsize=[6016/96,4016/96], dpi=96)
    plt.axes([0, 0, 1, 1], frameon=False)
    plt.imshow(ImageCopy[:,:,::-1])

    y_smooth = ReduceYNoise(file_x, file_y)
    
    plt.plot(file_x, file_y,linewidth=2,color='lime', linestyle='-')
    plt.plot(file_x, y_smooth,linewidth=1,color='yellow', linestyle='--')

    x_TipLong = Tip[0]
    y_TipLong = Tip[1]
    x_TipShort = Tip[2]
    y_TipShort = Tip[3]
    
    plt.plot(x_TipLong, y_TipLong,linewidth=5,color='darkorchid',zorder=1)
    plt.plot(x_TipShort, y_TipShort,linewidth=5,color='darkorchid',zorder=1)
    
    xMax = Results[6][:,0]
    yMax = Results[6][:,1]

    xMin = Results[7][:,0]
    yMin = Results[7][:,1]
    
    plt.plot(xMax, yMax, 'ro',zorder=1)
    plt.plot(xMin, yMin, 'bo',zorder=1)
    
    MaxLinePoints = Results[6]
    MaxLinePoints = MaxLinePoints[np.argsort(MaxLinePoints[:, 0])]
    
    MinLinePoints = Results[7]
    MinLinePoints = MinLinePoints[np.argsort(MinLinePoints[:, 0])]
    
    plt.plot(MaxLinePoints[:,0], MaxLinePoints[:,1],color='blue')
    plt.plot(MinLinePoints[:,0], MinLinePoints[:,1],color='blue')
    
    y_CenterLine,coefficients = FitCenterLine(file_x,y_smooth)
    plt.plot(file_x, y_CenterLine,color='steelblue')

    TipDiameter = Results[1][0]
    plt.plot(x_TipShort[-1], y_TipShort[-1], 'mo',zorder=1)
    plt.text(x_TipShort[-1], y_TipShort[-1], f'd={TipDiameter:.3f}', fontsize=8, color='gray', ha='center')
    

    for i in range(len(Results[1])):
        if Results[4][i] is not np.nan and Results[2][i] is not np.nan:
            plt.plot([Results[0][i][0],Results[4][i][0]], [Results[0][i][1],Results[4][i][1]],'gray', marker='*', linestyle='--', linewidth=1)
            mid_x = (Results[0][i][0] + Results[4][i][0]) / 2
            mid_y = (Results[0][i][1] + Results[4][i][1]) / 2       
            PU = (Results[2][i])/(PixelSize/1000)/VerticalScale
            plt.text(mid_x, mid_y, f'p={PU:.1f}', fontsize=8, color='gray', ha='center')
        

        if Results[5][i] is not np.nan and Results[3][i] is not np.nan:
            plt.plot([Results[0][i][0],Results[5][i][0]], [Results[0][i][1],Results[5][i][1]],'gray', marker='*', linestyle='--', linewidth=1)
            mid_x = (Results[0][i][0] + Results[5][i][0]) / 2
            mid_y = (Results[0][i][1] + Results[5][i][1]) / 2       
            PD = (Results[3][i])/(PixelSize/1000)/VerticalScale
            plt.text(mid_x, mid_y, f'p={PD:.1f}', fontsize=8, color='gray', ha='center')
        
        if Results[1][i] is not np.nan:
            DIA = (Results[1][i]) 
            plt.text(Results[0][i][0], Results[0][i][1], f'd={DIA:.3f}', fontsize=10, color='gray', ha='center')
       
    plt.axis('off')
    plt.show()      
    
def FindContoursIndex(contours):

    area=[]
    for i in range(len(contours)):
        cnt = contours[i]
        area.append( cv2.contourArea(cnt))
        #print(i ," area = ", area[i])
        
    srted_area_indexes = np.argsort(area) #sort area array from least to most
    
    results = []
    for i in range(2,6):
        index = srted_area_indexes[len(srted_area_indexes)-i]
        cntr = contours[index][:,0,:]
        average = np.mean(cntr, axis=0, keepdims=True)
        results.append([index,average[0].tolist()])
       
    max_x_index = max(range(len(results)), key=lambda i: results[i][1][0])
    number_with_max_x = results[max_x_index][0]
    
    # Get remaining elements
    remaining_elements = [result for result in results if result[0] != number_with_max_x]
    
    # Sort remaining elements based on the second element of their inner arrays
    remaining_sorted = sorted(remaining_elements, key=lambda x: x[1][1])  # Sort by second element
    
    # Extract largest, middle, and smallest based on the y values
    largest = remaining_sorted[-1]
    middle = remaining_sorted[1]
    smallest = remaining_sorted[0]
    
    VerticalGauge_Index = number_with_max_x
    TopGauge_Index = smallest[0]
    File_Index = middle[0]
    BottomGauge_Index = largest[0]

    return TopGauge_Index, BottomGauge_Index, VerticalGauge_Index, File_Index
   
def CalibrateImage(ImagePath,TopRealSize,BottomRealSize,RightRealSize):
    
    LW = 17
    DW = 1.2

    GrayscaleImage = cv2.imread(ImagePath,0) #0 means read in grayscale
    # GrayscaleImage = cv2.flip(GrayscaleImage, 0)

    GrayscaleImage[0:,0:200]=255 # L side of image
    GrayscaleImage[0:,-50:]=255 # R side of image
    GrayscaleImage[0:400,0:]=255 # T side of image
    GrayscaleImage[-400:,0:]=255 # B side of image

    # img_resized = cv2.resize(GrayscaleImage, (800, 600))
    # cv2.imshow('image',img_resized)
    # cv2.waitKey(0)

    LastError = 100
    BestThreshold = 100
    VError = LastError
    PixelSize = 4
    
    for threshold in range(90,190,5):
        
        ret, thresh = cv2.threshold(GrayscaleImage, threshold, 255, 0)
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_LIST  , cv2.CHAIN_APPROX_NONE)
        
        top_index,bottom_index,right_index,file_index = FindContoursIndex(contours)
        
        # ImageCopy = cv2.imread(ImagePath)
        # ImageCopy = cv2.flip(ImageCopy, 0)
        # cv2.drawContours(ImageCopy, contours, file_index, (255, 0, 0),50)
        # cv2.drawContours(ImageCopy, contours, top_index, (0, 255, 0),50)
        # cv2.drawContours(ImageCopy, contours, bottom_index, (0, 0, 255),50)
        # cv2.drawContours(ImageCopy, contours, right_index, (0, 255, 255),50)
        # plt.figure(figsize=[6016/96,4016/96])
        # plt.imshow(ImageCopy[:,:,::-1])
        # plt.axis('off')
        
        top = contours[top_index]
        top_Leftmost = tuple(top[top[:, :, 0].argmin()][0])
        top_Rightmost = tuple(top[top[:, :, 0].argmax()][0])
        topPixelLength = distance(top_Leftmost[0],top_Leftmost[1],top_Rightmost[0],top_Rightmost[1])
        
        bottom = contours[bottom_index]
        bottom_Leftmost = tuple(bottom[bottom[:, :, 0].argmin()][0])
        bottom_Rightmost = tuple(bottom[bottom[:, :, 0].argmax()][0])
        bottomPixelLength = distance(bottom_Leftmost[0],bottom_Leftmost[1],bottom_Rightmost[0],bottom_Rightmost[1])
        
        right = contours[right_index]
        right_North = tuple(right[right[:, :, 1].argmin()][0])
        right_South = tuple(right[right[:, :, 1].argmax()][0])
        rightPixelLength = distance(right_North[0],right_North[1],right_South[0],right_South[1])
        
        PixelSizeFromTop = TopRealSize/topPixelLength
        BottomSizeBasedOnTopPixelSize = PixelSizeFromTop*bottomPixelLength
        RightSizeBasedOnTopPixelSize = PixelSizeFromTop*rightPixelLength
        
        Error = (BottomSizeBasedOnTopPixelSize-BottomRealSize)*1000 #this number is in micromiters
        VerticalError = (RightSizeBasedOnTopPixelSize-RightRealSize)*1000 #this number is in micromiters
        
        if abs(Error)<abs(LastError):
            BestThreshold = threshold
            LastError = Error
            VError = VerticalError
            PixelSize = PixelSizeFromTop*1000
              
    #     print("Th = ",threshold,"\t","H_Error = ","{:.2f}".format(Error),"\t","V_Error = ","{:.2f}".format(VerticalError))
    # print("---------------------")
    
    

    file_x, file_y, file_index = FindContour(ImagePath,BestThreshold)
    y_smooth = ReduceYNoise(file_x, file_y)
    y_CenterLine,coefficients = FitCenterLine(file_x,y_smooth)
    slope, intercept = coefficients
    

    
    x_tip_index = np.argmax(file_x)
    y_tip_index = np.argmax(file_x)       
    x_tip = file_x[x_tip_index]
    y_tip = y_CenterLine[y_tip_index]

    Distance = -LW / PixelSize *1000
    xCenter_Wire = x_tip + Distance / np.sqrt(1 + slope**2)
    yCenter_Wire = y_tip - slope * (x_tip - xCenter_Wire)
    
    slopeNormal = -1/slope
    xNormal = np.arange(xCenter_Wire-10,xCenter_Wire+10,0.01)
    yNormal=slopeNormal*(xNormal-xCenter_Wire)+yCenter_Wire
    
    mask =  np.isin(file_x, xNormal.astype(int))
    
    selected_x = file_x[mask]
    selected_y = file_y[mask]
    
    mask = (selected_y>yCenter_Wire)
    
    selected_x_top = selected_x[mask]
    selected_y_top = selected_y[mask]
    
    selected_x_bot = selected_x[np.logical_not(mask)]
    selected_y_bot = selected_y[np.logical_not(mask)]
    
    Intersection1 = findIntersection(xNormal,yNormal,selected_x_top,selected_y_top)
    Intersection2 = findIntersection(xNormal,yNormal,selected_x_bot,selected_y_bot)

    WireDiameter = distance(Intersection1[0],Intersection1[1],Intersection2[0],Intersection2[1])
    WireDiameter = WireDiameter*(PixelSize/1000)

    VerticalScaling = DW/WireDiameter

    return PixelSize, VerticalScaling, BestThreshold, LastError

def FindContour(ImagePath,Threshold):
    GrayscaleImage = cv2.imread(ImagePath,0) #0 means read in grayscale
    
    GrayscaleImage[0:,0:300]=255 # L side of image
    GrayscaleImage[0:,-200:]=255 # R side of image
    GrayscaleImage[0:400,0:]=255 # T side of image
    GrayscaleImage[-400:,0:]=255 # T side of image

    ret, thresh = cv2.threshold(GrayscaleImage, Threshold, 255, 0)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_LIST  , cv2.CHAIN_APPROX_NONE)

    _,_,_,file_index = FindContoursIndex(contours)    

    file=contours[file_index][:,0,:] #extract a numpy array of file contour coordinate points 
    x=file[:,0] #extract x values from numpy array of file contour coordinate points 
    y=file[:,1] #extract y values from numpy array of file contour coordinate points
    
    return x,y,file_index

def ReduceYNoise(x,y):
    y_smooth = savgol_filter(y, 30, 1)
    return y_smooth

def FitCenterLine(x,y):
    
    coefficients = np.polyfit(x, y, 1) # best fit line through filtered yah
    slope, intercept = coefficients
    y_CenterLine = slope * x + intercept
    return y_CenterLine, coefficients

def TipInformation(x,y):
    tip_index = np.argmax(x)
    
    R2=1
    Interation = 10
    while R2>0.985:
        arrow_top=[]
        for i in range(6,3*Interation,3):
            arrow_top.append([x[tip_index+i], y[tip_index+i]])
            
        arrow_top = np.array(arrow_top)
            
        coefs = np.polyfit(arrow_top[:,0], arrow_top[:,1], 1)
        slope, intercept = coefs
        y_fit_top = np.polyval(coefs, arrow_top[:,0])
            
        R2 = r2_score(arrow_top[:,1], y_fit_top)
        Interation += 1
        #print(R2)
    coefs = np.polyfit(arrow_top[:-2,0], arrow_top[:-2,1], 1)
    m1,_ = coefs
 
    R2=1
    Interation = 10
    while R2>0.985:
        arrow_down=[]
        tip_index = np.argmax(x)
        for i in range(6,3*Interation,3):
            arrow_down.append([x[tip_index-i], y[tip_index-i]])
                
        arrow_down = np.array(arrow_down)
                
        coefs = np.polyfit(arrow_down[:,0], arrow_down[:,1], 1)
        slope, intercept = coefs
        y_fit_down = np.polyval(coefs, arrow_down[:,0])
                
        R2 = r2_score(arrow_down[:,1], y_fit_down)
        Interation += 1
        #print(R2)
    coefs = np.polyfit(arrow_down[:-2,0], arrow_down[:-2,1], 1)
    m2,_ = coefs  

    theta_radians = math.atan(abs((m1 - m2) / (1 + m1 * m2)))
    theta_degrees = math.degrees(theta_radians)
    lenTop = len(y_fit_top) 
    lenDown = len(y_fit_down) 
    
    if lenTop>lenDown:
        x_TipLong = arrow_top[:,0]
        y_TipLong = y_fit_top
        x_TipShort = arrow_down[:,0]
        y_TipShort = y_fit_down
    else:
        x_TipLong = arrow_down[:,0]
        y_TipLong = y_fit_down
        x_TipShort = arrow_top[:,0]
        y_TipShort = y_fit_top
        
    return theta_degrees, x_TipLong, y_TipLong, x_TipShort, y_TipShort

def FindLocalMaxMin(x, y,y_CenterLine,PixelSize):
    
    y_CenterLine, coefficients = FitCenterLine(x,y)
    
    tip_index = np.argmax(x)
    x_tip = x[tip_index]
    y_tip = y[tip_index]
    
    normal_tolerance = 1e-5
    OverFlute_tolerance = 1
    min_dist =40 
    
    Max_info,Min_info = InitialMinMaxCal(x, y, min_dist, normal_tolerance)
    
    x_top = Max_info[0]
    y_top = Max_info[1]
    Dis_top_peaks = Max_info[2]
    
    x_down = Min_info[0]
    y_down = Min_info[1]
    Dis_down_peaks = Min_info[2]
    
    x_localMax =[]
    y_localMax=[]

    x_localMin =[]
    y_localMin=[]
    
    for i in range(len(Dis_top_peaks)):
        index = Dis_top_peaks[i]
        point = [x_top[index],y_top[index]]
        PointOnCenterLine = find_normal_point(coefficients,point)
        DistanceToTip = distance(PointOnCenterLine[0],PointOnCenterLine[1],x_tip,y_tip)*PixelSize/1000
        #if(DistanceToTip<FluteLength):
        x_localMax.append(x_top[index])
        y_localMax.append(y_top[index])
            
    for i in range(len(Dis_down_peaks)):
        index = Dis_down_peaks[i]
        point = [x_down[index],y_down[index]]
        PointOnCenterLine = find_normal_point(coefficients,point)
        DistanceToTip = distance(PointOnCenterLine[0],PointOnCenterLine[1],x_tip,y_tip)*PixelSize/1000
        #if(DistanceToTip<FluteLength):
        x_localMin.append(x_down[index])
        y_localMin.append(y_down[index])

    
    x_localMax = np.array(x_localMax)
    y_localMax = np.array(y_localMax)
    x_localMin = np.array(x_localMin)
    y_localMin = np.array(y_localMin)
    
    max_order = np.lexsort([y_localMax, x_localMax])
    x_localMax = x_localMax[max_order]
    y_localMax = y_localMax[max_order]
    
    min_order = np.lexsort([y_localMin, x_localMin])
    x_localMin = x_localMin[min_order]
    y_localMin = y_localMin[min_order]

    # # Plot the results
    # plt.figure(figsize=(10, 6))
    # plt.plot(x, y, label="Contour", color="blue", linewidth=1.5)
    # plt.plot(x, y_CenterLine, label="Center Line", color="red", linestyle="--")
    # plt.scatter(x_localMax, y_localMax, color="green", label="Local Maxima", marker='*', s=100, zorder=5)
    # plt.scatter(x_localMin, y_localMin, color="orange", label="Local Minima", marker='o', s=100, zorder=5)
    # plt.scatter(x_tip, y_tip, color="purple", label="Tip", zorder=5)
    
    # plt.title("Local Maxima and Minima")
    # plt.xlabel("x")
    # plt.ylabel("y")
    # plt.legend()
    # plt.grid(True)
    # plt.gca().invert_yaxis()  # Invert y-axis if needed for image coordinates
    # plt.show()


    
    return x_localMax, y_localMax, x_localMin, y_localMin

def InitialMinMaxCal(x, y, min_dist, tolerance):

    y_CenterLine, [m,b] = FitCenterLine(x,y)
    
    # Separate points above and below the line
    above = y > y_CenterLine
    below = y < y_CenterLine
    
    x_top  = x[above]
    y_top  = y[above]
    top_order = np.lexsort([y_top, x_top])
    x_top = x_top[top_order]
    y_top = y_top[top_order]

    x_down = x[below]
    y_down = y[below]
    down_order = np.lexsort([y_down, x_down])
    x_down = x_down[down_order]
    y_down = y_down[down_order]
    
    Dis_top  = np.abs(m * x_top - y_top + b) / np.sqrt(m**2 + 1)
    Dis_down = np.abs(m * x_down - y_down + b) / np.sqrt(m**2 + 1)
    
    Dis_top_peaks = find_local_maxima(x_top,Dis_top, min_dist, tolerance)
    Dis_down_peaks = find_local_maxima(x_down,Dis_down, min_dist, tolerance)
    
    # plt.figure(figsize=[6016/96,4016/96], dpi=96)
    # plt.plot(x_top, Dis_top,linewidth=10,color='red', linestyle='-')
    # plt.plot(x_top[Dis_top_peaks], Dis_top[Dis_top_peaks], 'go', markersize=40, zorder=1)
    # plt.show() 
    
    # plt.figure(figsize=[6016/96,4016/96], dpi=96)
    # plt.plot(x_down, Dis_down,linewidth=10,color='green', linestyle='--')
    # plt.plot(x_down[Dis_down_peaks], Dis_down[Dis_down_peaks], 'ro', markersize=40, zorder=1)
    # plt.show() 
    
    Top_info = [x_top,y_top,Dis_top_peaks]
    Down_info = [x_down,y_down,Dis_down_peaks]
    return Top_info,Down_info

def find_local_maxima(X, Y, DST, tolerance=1e-5, gap_threshold=40):
    maxima = []
    maxima_indices = []
    n = len(Y)
    
    for i in range(DST, n - DST):
        is_maxima = True
        
        for j in range(1, DST + 1):
            # If gap_threshold is defined, check for disconnections
            if gap_threshold is not None and (X[i] - X[i - j] > gap_threshold or X[i + j] - X[i] > gap_threshold):
                continue  # Skip this neighbor due to a large gap
            
            # Allow some tolerance for "almost equal" points
            if Y[i] < Y[i - j] - tolerance or Y[i] < Y[i + j] - tolerance:
                is_maxima = False
                break
        
        if is_maxima:
            maxima.append(Y[i])
            maxima_indices.append(i)
    
    return maxima_indices

def CreateSpline(x_points,y_points):
    # Sort the data by x_localMax
    sorted_indices = np.argsort(x_points)
    x_points_sorted = x_points[sorted_indices]
    y_points_sorted = y_points[sorted_indices]

    # Create the cubic spline
    cs = CubicSpline(x_points_sorted, y_points_sorted)

    # Generate x and y values for plotting the spline
    x_spline = np.linspace(x_points_sorted.min(), x_points_sorted.max(), 100)
    return x_spline, cs

def CalculateTipDiameter(x,y,x_Tip,y_Tip,PixelSize):
    xx = x_Tip[-1]
    yy = y_Tip[-1]
    
    # m, b = coefficients
    # distance = math.sqrt((b+m*x-y)/(1 + m**2))
    
    # return distance
    
    # Fit a line using numpy's polyfit
    coefficients = np.polyfit(x, y, 1)
    slope, intercept = coefficients
    
    # Generate y values using the slope and intercept

    distance = np.abs(slope * xx - yy + intercept) / np.sqrt(slope**2 + 1)
    diameter = distance * 2 * PixelSize /1000 #in mm
    return distance,diameter
    
def Diameters(x,y_CenterLine,coefficients,x_spline,cs,distances,PixelSize):
    
    distances = np.array(distances) * (-1000/PixelSize)
    MinXOnSpline = min(x_spline)
    
    # Perpendicular direction vector to center line
    slope, intercept = coefficients
    perp_dx = -slope
    perp_dy = 1

    # Store intersection results
    intersections = []
    intersection_distances = []
    x_pointsOnLine = []
    y_pointsOnline = []

    x_pointsOnSpline = []
    y_pointsOnSpline = []

    for distance in distances[1:]:
        # Find the point at the desired distance
        x_tip_index = np.argmax(x)
        y_tip_index = np.argmax(x)
        
        x_end = x[x_tip_index]
        y_end = y_CenterLine[y_tip_index]

        x_point = x_end + distance / np.sqrt(1 + slope**2)
        y_point = y_end - slope * (x_end - x_point)

        # Define a function for finding the intersection
        def find_intersection(t):
            x_perp = x_point + t * perp_dx
            y_perp = y_point + t * perp_dy
            return cs(x_perp) - y_perp

        # Use fsolve to find the intersection
        t_intersection = fsolve(find_intersection, 0)[0]
        x_intersection = x_point + t_intersection * perp_dx
        y_intersection = y_point + t_intersection * perp_dy

        # Calculate the distance to the intersection
        intersection_distance = np.sqrt((x_intersection - x_point)**2 + (y_intersection - y_point)**2)
        intersections.append((x_intersection, y_intersection, intersection_distance))
        
        if x_intersection > MinXOnSpline:
                    
            x_pointsOnSpline.append(x_intersection)
            y_pointsOnSpline.append(y_intersection)
            
            intersection_distances.append(intersection_distance)
            
        x_pointsOnLine.append(x_point)
        y_pointsOnline.append(y_point)

    x_pointsOnLine = np.array(x_pointsOnLine)
    y_pointsOnline = np.array(y_pointsOnline)
    x_pointsOnSpline = np.array(x_pointsOnSpline)
    y_pointsOnSpline = np.array(y_pointsOnSpline)
    intersection_distances = np.array(intersection_distances)
    
    return x_pointsOnLine,y_pointsOnline,x_pointsOnSpline,y_pointsOnSpline,intersection_distances

def MeasureD(x,y,Result_Max,Result_Min,TipDiameter,PixelSize):
    x_centerLinePoints = Result_Max[0]
    y_centerLinePoints = Result_Max[1]
    
    x_max = Result_Max[2]
    d_max = Result_Max[4]
    x_min = Result_Min[2]
    d_min = Result_Min[4]
    
    leng = max(len(x_max),len(x_min)) #1 is for the tip.
    Measured_Diameters = []
    CenterPoints = []
    
    Measured_Diameters.append(TipDiameter)
    
    
    for i in range(leng):
        if len(x_max)>i and len(x_min)>i:
            D_max = d_max[i]
            D_min = d_min[i]
            x_center = x_centerLinePoints[i]
            y_center = y_centerLinePoints[i]
        elif len(x_max)>i and len(x_min)<=i:
            D_max = d_max[i]
            D_min = d_max[i]
            x_center = x_centerLinePoints[i]
            y_center = y_centerLinePoints[i]
        elif len(x_max)<=i and len(x_min)>i:
            D_max = d_min[i]
            D_min = d_min[i]
            x_center = x_centerLinePoints[i]
            y_center = y_centerLinePoints[i]
            
        D = (D_max + D_min)*(PixelSize/1000)
        Measured_Diameters.append(D)
        CenterPoints.append([x_center,y_center])

    
    x_centerLastPoint = x_centerLinePoints[-1]
    y_centerLastPoint = y_centerLinePoints[-1]
    slope = (y_centerLinePoints[-1]-y_centerLinePoints[0])/(x_centerLinePoints[-1]-x_centerLinePoints[0])
    
    slopeNormal = -1/slope
    xNormal = np.arange(x_centerLastPoint-10,x_centerLastPoint+10,0.01)
    yNormal=slopeNormal*(xNormal-x_centerLastPoint)+y_centerLastPoint
    
    mask =  np.isin(x, xNormal.astype(int))
    
    selected_x = x[mask]
    selected_y = y[mask]
    
    mask = (selected_y>y_centerLastPoint)
    
    selected_x_top = selected_x[mask]
    selected_y_top = selected_y[mask]
    
    selected_x_bot = selected_x[np.logical_not(mask)]
    selected_y_bot = selected_y[np.logical_not(mask)]
    
    Intersection1 = findIntersection(xNormal,yNormal,selected_x_top,selected_y_top)
    Intersection2 = findIntersection(xNormal,yNormal,selected_x_bot,selected_y_bot)

    LastDistance = distance(Intersection1[0],Intersection1[1],Intersection2[0],Intersection2[1])
    LastDistance = LastDistance*(PixelSize/1000)
    
    Measured_Diameters.append(LastDistance)
    CenterPoints.append([x_centerLastPoint,y_centerLastPoint])
    
    # plt.plot(xNormal,yNormal)
    # plt.plot(selected_x_top,selected_y_top,color='lime')
    # plt.plot(selected_x_bot,selected_y_bot,color='lime')
    # plt.plot(Intersection1[0], Intersection1[1], 'ro')
    # plt.plot(Intersection2[0], Intersection2[1], 'ro')
    # plt.show()
    
    return Measured_Diameters,CenterPoints,np.array([Intersection1,Intersection2])

def findIntersection(x1,y1,x2,y2):
    long = len(x1)
    short = len(x2)
    dmin = 1000
    for i in range(long):
        for j in range(short):
            d = distance(x1[i],y1[i],x2[j],y2[j])
            if(d<dmin):
                dmin = d
                i_Min = i
                j_min = j
                
    return [x1[i_Min],y2[j_min]]

def distance(x1,y1,x2,y2):
    d = math.sqrt((x2-x1)**2+(y2-y1)**2)
    return d

def find_UpperLowerPoints(xPeak, yPeak, XonC, YonC, mCntr, bCntr):
    
    mNrml = -1 / mCntr
    bNrml = YonC - mNrml * XonC
    
    D = np.abs(mNrml * xPeak - yPeak + bNrml) / np.sqrt(mNrml**2 + 1)
    D_order_indexes = np.argsort(D)
    
    indx1 = D_order_indexes[0]
    indx2 = D_order_indexes[1]
    
    if xPeak[indx1] == xPeak[indx2]:
        indx2 = D_order_indexes[2]

    return [xPeak[indx1],yPeak[indx1]],[xPeak[indx2],yPeak[indx2]]
        
def XnY_OnCenterLine(x_tip, y_tip, y_CenterLine, coefficients, D, PixelSize):
    
    Distance = -D / PixelSize *1000
    slope, intercept = coefficients
    
    X = x_tip + Distance / np.sqrt(1 + slope**2)
    Y = y_tip - slope * (x_tip - X)
    
    return X,Y
    
def find_normal_point(coefficients, IND):
    slope, intercept = coefficients
    x_ind, y_ind = IND
    
    # Slope of the normal line
    normal_slope = -1 / slope
    
    # Solve for x
    x_normal = (y_ind - normal_slope * x_ind - intercept) / (slope - normal_slope)
    
    # Now find y using the original line equation
    y_normal = slope * x_normal + intercept
    
    return [x_normal, y_normal]    
    
def find_boundary_points(PointsArray, PNT, coefficients):
    slope, intercept = coefficients
    x_pnt, y_pnt = PNT
    
    
    normal_slope = -1 / slope
    normal_intercept = y_pnt - normal_slope * x_pnt
    
    lower_point = None
    upper_point = None
    
    for point in PointsArray:
        x, y = point
        if y_pnt<y:
            # Check if the point is below the normal line
            
            if y < (normal_slope * x + normal_intercept):
                lower_point = point  # Update the lower point
            # Check if the point is above the normal line
            elif y > (normal_slope * x + normal_intercept):
                upper_point = point  # Update the upper point
 
                
        if y_pnt>y:
            # Check if the point is below the normal line
            if y > (normal_slope * x + normal_intercept):
                lower_point = point  # Update the lower point
            # Check if the point is above the normal line
            elif y < (normal_slope * x + normal_intercept):
                upper_point = point  # Update the upper point
                
        if lower_point is not None and upper_point is not None:
            break
    
    # Ensure we have found both points
    if lower_point is not None and upper_point is not None:
        return lower_point, upper_point
    else:
        return None, None
    
def distance_and_intersection(A, B, CenterPoint):
    x_A, y_A = A
    x_B, y_B = B
    x_P, y_P = CenterPoint
    
    # Calculate the slope of the line AB
    slope_AB = (y_B - y_A) / (x_B - x_A) if (x_B - x_A) != 0 else float('inf')
    
    # Calculate the slope of the normal line
    if slope_AB != 0:
        normal_slope = -1 / slope_AB
    else:
        normal_slope = float('inf')  # Normal is vertical if AB is horizontal
    
    # Calculate the intersection point
    if normal_slope != float('inf'):
        # Normal line equation: y - y_P = normal_slope * (x - x_P)
        # Rearranged: y = normal_slope * (x - x_P) + y_P
        # Line AB equation: y = slope_AB * (x - x_A) + y_A
        # Set them equal to find x intersection
        x_inter = (normal_slope * x_P - slope_AB * x_A + y_A - y_P) / (normal_slope - slope_AB)
        y_inter = slope_AB * x_inter + y_A - slope_AB * x_A
    else:
        # If the normal is vertical, the intersection point is directly above or below CenterPoint
        x_inter = x_P
        y_inter = slope_AB * x_inter + y_A - slope_AB * x_A
        
    intersection_point = [x_inter, y_inter]
    
    # Calculate the distance using the previously defined formula
    numerator = abs((y_B - y_A) * x_P - (x_B - x_A) * y_P + (x_B - x_A) * y_A - (y_B - y_A) * x_A)
    denominator = ((y_B - y_A) ** 2 + (x_B - x_A) ** 2) ** 0.5
    
    distance = numerator / denominator
    return distance, intersection_point
    
def FindDistanceFromContour(x,y,x_center,y_center,coeffs):
   
    slope, intercept = coeffs
    
    slopeNormal = -1/slope
    xNormal = np.arange(x_center-10,x_center+10,0.01)
    yNormal=slopeNormal*(xNormal-x_center)+y_center
    
    mask =  np.isin(x, xNormal.astype(int))
    
    selected_x = x[mask]
    selected_y = y[mask]
    
    mask = (selected_y>y_center)
    
    selected_x_top = selected_x[mask]
    selected_y_top = selected_y[mask]
    
    selected_x_bot = selected_x[np.logical_not(mask)]
    selected_y_bot = selected_y[np.logical_not(mask)]
    
    Intersection_top = findIntersection(xNormal,yNormal,selected_x_top,selected_y_top)
    Intersection_bot = findIntersection(xNormal,yNormal,selected_x_bot,selected_y_bot)

    Distance_top = distance(Intersection_top[0],Intersection_top[1],x_center,y_center)
    Distance_bot = distance(Intersection_bot[0],Intersection_bot[1],x_center,y_center)
    
    return Distance_top,Intersection_top,Distance_bot,Intersection_bot

def distance_and_intersection_N(A, B, CenterPoint, m_Center, b_Center):
    # Unpack points
    x1, y1 = A
    x2, y2 = B
    xc, yc = CenterPoint

    # Calculate the slope and intercept of ABLine
    if x2 - x1 != 0:
        m_AB = (y2 - y1) / (x2 - x1)
        b_AB = y1 - m_AB * x1  # y = mx + b => b = y - mx
    else:
        # Vertical line case
        m_AB = None  # Undefined slope (vertical line)
        b_AB = None

    # Calculate the slope of the normal line
    if m_Center is not None:
        m_normal = -1 / m_Center
    else:
        # Normal line is horizontal
        m_normal = 0

    # Equation of the normal line: y - yc = m_normal * (x - xc)
    # Rearranging to y = m_normal * (x - xc) + yc
    def normal_line(x):
        return m_normal * (x - xc) + yc

    # Find intersection point
    if m_AB is not None:
        # Find intersection with ABLine
        if m_normal is not None:
            # Solve m_AB * x + b_AB = m_normal * x + (yc - m_normal * xc)
            # (m_AB - m_normal) * x = (yc - m_normal * xc) - b_AB
            x_i = ((yc - m_normal * xc) - b_AB) / (m_AB - m_normal)
            y_i = m_AB * x_i + b_AB
        else:
            # If normal line is vertical, the intersection point is directly above or below CenterPoint
            x_i = xc
            y_i = m_AB * x_i + b_AB
    else:
        # If ABLine is vertical (x = x1)
        x_i = x1
        if m_normal is not None:
            y_i = normal_line(x_i)
        else:
            y_i = yc  # Both lines are vertical

    # Calculate distance from CenterPoint to intersection point
    distance = math.sqrt((x_i - xc) ** 2 + (y_i - yc) ** 2)

    return distance, [x_i, y_i]
      
def normal_distance_PointToLine(point, coefs, PixelSize):
    x, y = point
    slope, intercept = coefs

    # Coefficients of the line equation Ax + By + C = 0
    A = slope
    B = -1
    C = intercept

    # Calculate the distance
    distance = abs(A * x + B * y + C) / np.sqrt(A**2 + B**2)
    distance = distance * PixelSize/1000
    return distance   
    
def CalTipDiaFromMinMaxPoints(file_x, file_y, PixelSize, VerticalScale):
    #Smooth the y values to reduce noise
    y_smooth = ReduceYNoise(file_x, file_y)

    #fit a center line through x and y points
    y_CenterLine,coefficients = FitCenterLine(file_x,y_smooth)
    CenterLineCoefs = coefficients

    #find the information of tip
    theta_degrees, x_TipLong, y_TipLong, x_TipShort, y_TipShort = TipInformation(file_x, y_smooth)
    TipPixels,TipDiameter = CalculateTipDiameter(file_x,y_smooth,x_TipShort,y_TipShort,PixelSize)
    x_tip_index = np.argmax(file_x)
    y_tip_index = np.argmax(file_x)       
    x_tip = file_x[x_tip_index]
    y_tip = y_CenterLine[y_tip_index]
    
    xMax, yMax, xMin, yMin = FindLocalMaxMin(file_x, y_smooth,y_CenterLine,PixelSize)

    xMax = xMax[-3:]
    yMax = yMax[-3:]
    xMin = xMin[-3:]
    yMin = yMin[-3:]
    
    weights_Max = 2*np.arange(0 ,len(xMax), 1)
    weights_Min = 2*np.arange(0 ,len(xMin), 1)
    
    # weights_Max = 2*np.arange(len(xMax) ,0, -1)
    # weights_Min = 2*np.arange(len(xMin) ,0, -1)
    
    
    MaxLineCoefs = np.polyfit(xMax, yMax, 1, w=weights_Max)
    MinLineCoefs = np.polyfit(xMin, yMin, 1, w=weights_Min)
    
    # plt.plot(file_x,file_y)
    # plt.plot(xMax,yMax)
    # plt.plot(xMin,yMin)
    # plt.plot(xMax,np.polyval(MaxLineCoefs,xMax))
    # plt.plot(xMin,np.polyval(MinLineCoefs,xMin))
    # plt.show()
    
    m_A = MaxLineCoefs[0]
    b_A = MaxLineCoefs[1]
    m_B = MinLineCoefs[0]
    b_B = MinLineCoefs[1]
    m_C = CenterLineCoefs[0]
    b_C = CenterLineCoefs[1]
    
    IntersectMax,IntersectMin,PixelD_tip = TwoLinesAndNormalToCenterLine(m_A, b_A, m_B, b_B, m_C, b_C, x_tip, y_tip)
    
    # plt.plot(file_x, file_y,linewidth=2,color='lime', linestyle='-')
    # plt.plot(xMax, MaxLineCoefs[0] * xMax + MaxLineCoefs[1],linewidth=2,color='red', linestyle='-')
    # plt.plot(xMin, MinLineCoefs[0] * xMin + MinLineCoefs[1],linewidth=2,color='red', linestyle='-')
    # plt.plot(IntersectMax[0],IntersectMax[1],"ro")
    # plt.plot(IntersectMin[0],IntersectMin[1],"ro")
    # plt.plot(xMax, yMax, 'ro',zorder=1)
    # plt.plot(xMin, yMin, 'bo',zorder=1)
    # plt.gca().invert_yaxis()
    # plt.show()
    
    D_tip = PixelD_tip * PixelSize/1000 * VerticalScale
    return D_tip, IntersectMax, IntersectMin

def TwoLinesAndNormalToCenterLine(m_A, b_A, m_B, b_B, m_C, b_C, x_0, y_0):
    m_N = -1 / m_C

    # Find intersection with Line_A
    x_A = (-b_A - m_N * x_0 + y_0) / (m_A - m_N)
    y_A = m_A * x_A + b_A

    # Find intersection with Line_B
    x_B = (-b_B - m_N * x_0 + y_0) / (m_B - m_N)
    y_B = m_B * x_B + b_B

    # Calculate distance between two points
    distance = math.sqrt((x_B - x_A) ** 2 + (y_B - y_A) ** 2)

    return (x_A, y_A), (x_B, y_B), distance

























