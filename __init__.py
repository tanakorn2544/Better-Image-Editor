bl_info = {
    "name": "Better Image Editor",
    "author": "Korn Sensei",
    "version": (1, 2),
    "blender": (4, 0, 0),
    "location": "Image Editor > Sidebar > Better Image",
    "description": "Screenshot capture, drawing/highlighting tools, and clipboard integration for Image Editor",
    "category": "Image",
}

import importlib
import bpy
from . import properties
from . import operators
from . import ui
from . import drawing
from . import clipboard
from . import recording
from . import icons
from . import keymap

modules = [
    properties,
    operators,
    ui,
    drawing,
    clipboard,
    recording,
    icons,
    keymap,
]

def register():
    for m in modules:
        importlib.reload(m)
        
    properties.register()
    operators.register()
    ui.register()
    drawing.register()
    recording.register()
    icons.register()
    keymap.register()

def unregister():
    keymap.unregister()
    icons.unregister()
    drawing.unregister()
    recording.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()

if __name__ == "__main__":
    register()
