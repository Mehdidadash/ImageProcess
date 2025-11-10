import os, sys
print('CWD:', os.getcwd())
print('SYS.PATH[0]:', sys.path[0])
# Ensure project root is on sys.path (script runs from scripts/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
print('ADDED_PROJECT_ROOT:', project_root)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    import CameraAppClass
    print('IMPORT_OK')
except Exception:
    import traceback
    traceback.print_exc()
