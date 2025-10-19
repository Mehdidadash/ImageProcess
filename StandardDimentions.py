import numpy as np
import os


def read_info(folder_name, base_dir="StandardDimentions"):

    # Construct the path to the text file
    file_path = os.path.join(base_dir, folder_name, f"{folder_name}.txt")
    
    # Check if the file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    # Initialize storage for variables and arrays
    variables = {}
    arrays = {}
    current_label = None

    # Read the file
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("---"):  # Skip separator lines
                continue
            elif "=" in line:  # Detect scalar variables
                key, value = line.split("=")
                variables[key.strip()] = float(value.strip())
            elif line.isalpha():  # Detect array labels (e.g., "Diameters", "Pitch")
                current_label = line
                arrays[current_label] = []
            elif current_label:  # Add data to the current array
                arrays[current_label].append(list(map(float, line.split(','))))

    # Convert lists to numpy arrays for arrays
    for label in arrays:
        arrays[label] = np.array(arrays[label])

    return {"variables": variables, "arrays": arrays}
    
def read_ESLH_values(folder_name, base_dir="StandardDimentions"):

    # Construct the full path to the subfolder
    folder_path = os.path.join(base_dir, folder_name)
    
    # Check if the folder exists
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder '{folder_path}' not found.")
    
    # List to store numpy arrays
    arrays = []
    
    # Iterate through all files in the given folder
    for file_name in sorted(os.listdir(folder_path)):  # Sort to ensure files are processed in order
        # Check if the file matches the required format
        if file_name.startswith(f"{folder_name}-ESLH-") and file_name.endswith(".txt"):
            # Construct the full file path
            file_path = os.path.join(folder_path, file_name)
            
            # Read the file contents and convert to a numpy array
            try:
                with open(file_path, "r") as file:
                    # Read all lines, strip whitespace, and convert to float
                    data = np.array([float(line.strip()) for line in file if line.strip()])
                    # Append the array to the list
                    arrays.append(data)
            except Exception as e:
                print(f"Error reading file {file_name}: {e}")
    
    # Return a tuple of numpy arrays
    return tuple(arrays)