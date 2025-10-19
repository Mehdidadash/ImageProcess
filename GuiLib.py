import PySimpleGUI as sg
import ImageProcessLib as IPL
import DrawLib as DrawLib
import os.path
import numpy as np
from datetime import date


def MainGUI():
    FileType = []            
    CameraLayout1 = [
                        sg.In(size=(50,1),enable_events=True,key="-FolderDir-"),
                        sg.FolderBrowse(),
        ],[
                        sg.Listbox(values=[],enable_events=True,key="-FolderList-",size=(55,5))
        ],
    
    CameraLayout2 = [
                        sg.Text("Name: "),
                        sg.In(size=(39,1),enable_events=True,key="-ImageName-"),
                        sg.Button("Take Image"),
        ],[
                        
           ],
    
    CameraLayout = [sg.Frame("Folder",CameraLayout1)],[sg.Frame("Image",CameraLayout2)]
    
    ProcessLayout = [
                        sg.Radio('SX', group_id=1, key="-Radio_SX-"), 
                        sg.Radio('S1', group_id=1, key="-Radio_S1-"), 
                        sg.Radio('S2', group_id=1, key="-Radio_S2-"),
                        sg.Radio('F1', group_id=1, key="-Radio_F1-"),
                        sg.Radio('F2', group_id=1, key="-Radio_F2-"),
                        sg.Radio('F3', group_id=1, key="-Radio_F3-"),
        ],[
                       sg.Button("Process Image"),
           ]

    DrawLayout = [
                       sg.Radio('Reolix', group_id=2, key="-Radio_Reolix-",default=True), 
                       sg.Radio('Triangle', group_id=2, key="-Radio_Triangle-"), 
           ],[
                       sg.Radio('Single Surface', group_id=3, key="-Radio_SingleGeo-"), 
                       sg.Radio('Full geometry', group_id=3, key="-Radio_FullGeo-", default=True), 
           ],[
                       sg.Radio('Draw Helix line', group_id=4, key="-Radio_Helix-",default=True), 
                       sg.Radio('No Helix line', group_id=4, key="-Radio_NoHelix-"), 
           ],[
                       sg.Button("Draw 3D model"),
           ],

    CNCLayout = [
                       sg.Text("step size: ",),
                       sg.In(default_text=0.01, size=(20,1),enable_events=True,key="-stepSize-",),
           ],[
                       sg.Text("maximum feed: ",),
                       sg.In(default_text=2000, size=(20,1),enable_events=True,key="-maxfeed-",),
           ],[
                       sg.Radio('Simple', group_id=5, key="-Radio_SimpleCNC-",default=True), 
                       sg.Radio('Reolix', group_id=5, key="-Radio_ReolixCNC-"), 
           ],[
                       sg.Button("Create CNC code"),
                  ],       
    
    
    layout = \
        [sg.Frame("Camera",CameraLayout,title_location=sg.TITLE_LOCATION_TOP)],\
        [sg.Frame("Process",ProcessLayout,title_location=sg.TITLE_LOCATION_TOP)],\
        [sg.Frame("3D Visualization",DrawLayout,title_location=sg.TITLE_LOCATION_TOP)],\
        [sg.Frame("CNC Code",CNCLayout,title_location=sg.TITLE_LOCATION_TOP)],\
    
    window = sg.Window("Endo",layout, margins=(10,10))
    
    while True:
        event, values = window.read()
        
        if event == sg.WINDOW_CLOSED:
            break
        
        if event == "-FolderDir-":
            folder = values["-FolderDir-"]
            if  os.path.isdir(values["-FolderDir-"]):
                file_list = os.listdir(folder)
                window["-FolderList-"].update(file_list)
            
        if event == "Take Image":
            if values["-FolderDir-"] == "" :
                sg.popup_ok("First, Select the save folder")
                
            elif not os.path.isdir(values["-FolderDir-"]):
                sg.popup_ok("That is not a correct DIR, Select folder again!")
                
            elif values["-ImageName-"] == "" :
                sg.popup_ok("Enter a name for the new image")
                
            elif not is_valid_filename(values["-ImageName-"]):
                sg.popup_ok("That is not a valid name for a file")
                
            else:
                print(values["-ImageName-"])
                file_list = os.listdir(folder)
                window["-FolderList-"].update(file_list)
                
        if event == "Process Image":
            # Check which radio button is selected
            if values["-Radio_SX-"]:
                FileType = "SX"
            elif values["-Radio_S1-"]:
                FileType = "S1"
            elif values["-Radio_S2-"]:
                FileType = "S2"
            elif values["-Radio_F1-"]:
                FileType = "F1"
            elif values["-Radio_F2-"]:
                FileType = "F2"
            elif values["-Radio_F3-"]:
                FileType = "F3"
            else:
                FileType = []
                sg.popup_ok("Select a type")
            
            if FileType != []:
                if values["-FolderDir-"] == "" :
                    sg.popup_ok("First, Select the save folder")
                    
                elif not os.path.isdir(values["-FolderDir-"]):
                    sg.popup_ok("That is not a correct DIR, Select folder again!")
                else:
                    try:
                        Average_Error = IPL.MAIN(folder,FileType)
                        if sg.popup_yes_no("Do you want to save the average errors?",auto_close=True,auto_close_duration=10,keep_on_top=True) == "Yes" :
                            #saveFolder = sg.popup_get_folder("Select Folder to save", default_path = folder, no_window = True)
                            
                            filename = sg.tk.filedialog.asksaveasfilename(
                            defaultextension='txt',
                            filetypes=(("TXT File", "*.txt"),),
                            initialdir=folder,
                            parent=window.TKroot,
                            title="Save As"
                            )
                            try:
                                np.savetxt(filename, Average_Error, fmt='%.4f')
                            except:
                                print('Save failed!')
                            else:
                                print('File Saved')
                                sg.popup_ok("File Saved")
                    except:
                        print("Something went wrong on process")
                        sg.popup_ok("Something went wrong on process")
                        
        if event == "Draw 3D model":
            # Check which radio button is selected
            if values["-Radio_SX-"]:
                FileType = "SX"
            elif values["-Radio_S1-"]:
                FileType = "S1"
            elif values["-Radio_S2-"]:
                FileType = "S2"
            elif values["-Radio_F1-"]:
                FileType = "F1"
            elif values["-Radio_F2-"]:
                FileType = "F2"
            elif values["-Radio_F3-"]:
                FileType = "F3"
            else:
                FileType = []
                sg.popup_ok("Select a type")
                
            if values["-Radio_Reolix-"]:
                Section = "reolix"
            elif values["-Radio_Triangle-"]:
                Section = "line"

            if values["-Radio_SingleGeo-"]:
                SingleSurface = True
            elif values["-Radio_FullGeo-"]:
                SingleSurface = False

            if values["-Radio_Helix-"]:
                drawHelix = True
            elif values["-Radio_NoHelix-"]:
                drawHelix = False
            
            if FileType != []:
                try:
                    DrawLib.Draw3D(FileType, Section, drawHelix, SingleSurface)
                except:
                    print("Something went wrong on process")
                    sg.popup_ok("Something went wrong on process")

        if event == "Create CNC code":
            # Check which radio button is selected
            if values["-Radio_SX-"]:
                FileType = "SX"
            elif values["-Radio_S1-"]:
                FileType = "S1"
            elif values["-Radio_S2-"]:
                FileType = "S2"
            elif values["-Radio_F1-"]:
                FileType = "F1"
            elif values["-Radio_F2-"]:
                FileType = "F2"
            elif values["-Radio_F3-"]:
                FileType = "F3"
            else:
                FileType = []
                sg.popup_ok("Select a type")
            
            if values["-Radio_SimpleCNC-"]:
                IsReolix = False
            elif values["-Radio_ReolixCNC-"]:
                IsReolix = True
                

            if FileType != []:
                try:
                    savefilename = sg.tk.filedialog.asksaveasfilename(
                    defaultextension='.ngc',
                    filetypes=(("ngc File", "*.ngc"),),
                    parent=window.TKroot,
                    initialfile = FileType + "_V01_" + date.today().strftime("%Y-%m-%d"),
                    title="Save As"
                    )
                    stepsize = float(values["-stepSize-"])
                    maxfeed = float(values["-maxfeed-"])

                    if (DrawLib.create_CNC_code(FileType, stepsize, maxfeed, savefilename, IsReolix)):
                        sg.popup_ok("Code created successfully")
                except:
                    print("Something went wrong on process")
                    sg.popup_ok("Something went wrong on process")
                                                        

    window.close()

def is_valid_filename(filename):
    # Forbidden characters in Windows filenames
    forbidden_chars = '<>:"/\\|?*'

    # Check for forbidden characters
    if any(char in filename for char in forbidden_chars):
        return False

    # Check if the filename ends with a space or period (invalid in Windows)
    if filename.endswith(' ') or filename.endswith('.'):
        return False

    return True
































