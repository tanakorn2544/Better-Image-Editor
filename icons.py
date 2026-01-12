import bpy
import os
import bpy.utils.previews

# Global dictionary to store preview collections
preview_collections = {}

def get_icon(name):
    """Get icon ID by name (without extension)"""
    pcoll = preview_collections.get("main")
    if not pcoll: return 0
    icon = pcoll.get(name)
    return icon.icon_id if icon else 0

def register():
    pcoll = bpy.utils.previews.new()
    
    # Icons directory
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    
    # Load icons
    # Helper to load safely
    def load(name, filename):
        path = os.path.join(icons_dir, filename)
        if os.path.exists(path):
            pcoll.load(name, path, 'IMAGE')
            
    load("tool_move", "tool_move.png")
    load("tool_draw", "tool_draw.png")
    load("tool_text", "tool_text.png")
    load("tool_crop", "tool_crop.png")
    load("tool_arrow", "tool_arrow.png")
    load("tool_rect", "tool_rect.png")
    load("tool_circle", "tool_circle.png")
    load("tool_highlight", "tool_highlight.png")
    
    preview_collections["main"] = pcoll

def unregister():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
