import os, sys, traceback, importlib
print('CWD:', os.getcwd())
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
print('PROJECT_ROOT:', project_root)
# run headless for Qt
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
modules = [
    'PyQt5', 'PyQt5.QtWidgets', 'CameraParams_header', 'MvCameraControl_class',
    'CameraWorkerClass', 'ImageProcessLib', 'CameraAppClass'
]
for m in modules:
    try:
        print('\nIMPORT ->', m)
        importlib.import_module(m)
        print('OK ->', m)
    except Exception:
        print('ERROR importing', m)
        traceback.print_exc()
        break
print('\nDIAG DONE')
