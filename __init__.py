bl_info = {
    "name": "Better Image Editor",
    "author": "Korn Sensei",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Image Editor > Sidebar > Better Image",
    "description": "Screenshot capture, drawing/highlighting tools, and clipboard integration for Image Editor",
    "category": "Image",
}

import bpy
from . import properties
from . import operators
from . import ui
from . import drawing
from . import clipboard
from . import icons
from . import keymap

def register():
    properties.register()
    operators.register()
    ui.register()
    drawing.register()
    icons.register()
    keymap.register()

def unregister():
    keymap.unregister()
    icons.unregister()
    drawing.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()

if __name__ == "__main__":
    register()
