"""
UI Panel for Better Image Editor addon.
"""

import bpy
from bpy.types import Panel, UIList
from . import icons


class BETTERIMG_UL_layer_list(UIList):
    """Custom Layer List"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "is_visible", text="", icon='HIDE_OFF' if item.is_visible else 'HIDE_ON', emboss=False)
            row.prop(item, "name", text="", emboss=False)
            row.prop(item, "is_locked", text="", icon='LOCKED' if item.is_locked else 'UNLOCKED', emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class BETTERIMG_PT_layers(Panel):
    """Layers Panel"""
    bl_label = "Layers"
    bl_idname = "BETTERIMG_PT_layers"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Better Image"
    
    def draw(self, context):
        layout = self.layout
        data = context.scene.better_image_data
        
        row = layout.row()
        row.template_list("BETTERIMG_UL_layer_list", "layers", data, "layers", data, "active_layer_index")
        
        col = row.column(align=True)
        col.operator("better_image.add_layer", icon='ADD', text="")
        col.operator("better_image.remove_layer", icon='REMOVE', text="")


class BETTERIMG_PT_main_panel(Panel):
    """Main panel in Image Editor sidebar"""
    bl_label = "Better Image Editor"
    bl_idname = "BETTERIMG_PT_main_panel"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Better Image"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.better_image_editor
        
        # Capture Section
        box = layout.box()
        box.label(text="Capture", icon='RESTRICT_RENDER_OFF')
        row = box.row(align=True)
        row.operator("better_image.capture_screen", text="Screen", icon='DESKTOP')
        row.operator("better_image.paste_from_clipboard", text="Paste", icon='PASTEDOWN')
        
        layout.separator()
        
        # Tools Grid
        box = layout.box()
        box.label(text="Tools", icon='TOOL_SETTINGS')
        
        grid = box.grid_flow(columns=3, align=True)
        
        def tool_btn(tool_id, icon, name, custom_name=None):
            is_active = props.active_tool == tool_id
            icon_id = icons.get_icon(custom_name) if custom_name else 0
            
            if icon_id:
                op = grid.operator("better_image.set_tool", text=name, icon_value=icon_id, depress=is_active)
            else:
                op = grid.operator("better_image.set_tool", text=name, icon=icon, depress=is_active)
            op.tool = tool_id

        tool_btn('MOVE', 'RESTRICT_SELECT_OFF', "", "tool_move")
        tool_btn('DRAW', 'GREASEPENCIL', "", "tool_draw")
        tool_btn('ERASER', 'BRUSH_DATA', "", "tool_eraser") # Eraser
        tool_btn('HIGHLIGHT', 'MARKER_HLT', "", "tool_highlight")
        tool_btn('ARROW', 'MOD_PARTICLES', "", "tool_arrow") 
        tool_btn('RECTANGLE', 'MESH_CUBOID', "", "tool_rect")
        tool_btn('ELLIPSE', 'MESH_CIRCLE', "", "tool_circle")
        tool_btn('TEXT', 'SMALL_CAPS', "", "tool_text")

        tool_btn('CROP', 'BORDERMOVE', "", "tool_crop")
        tool_btn('PIXELATE', 'NODE_COMPOSITING', "", "tool_pixelate")
        
        # Tool Settings
        layout.separator()
        box = layout.box()
        
        if props.active_tool == 'MOVE':
            box.label(text="Select & Move", icon='HAND')
            
            # Text Editing UI
            txt = props.selected_text
            if txt:
                box.label(text="Edit Selected Text:", icon='TEXT')
                box.prop(props, "selected_text", text="")
            
            if props.selected_item_size > 0:
                 box.prop(props, "selected_item_size", text="Edit Size")
                 box.separator()
            
            box.label(text="Drag items to move", icon='INFO')
            box.operator("better_image.delete_selected", text="Delete Selected", icon='TRASH')
            
        elif props.active_tool == 'TEXT':
            box.label(text="Text Settings", icon='FONT_DATA')
            box.prop(props, "brush_color", text="Color")
            box.prop(props, "text_size", text="Size")
            
            # Smart Text Settings
            row = box.row(align=True)
            row.prop(props, "text_show_bg", text="Background")
            if props.text_show_bg:
                row.prop(props, "text_bg_color", text="")
                
            row = box.row(align=True)
            row.prop(props, "text_show_shadow", text="Shadow")
            if props.text_show_shadow:
                row.prop(props, "text_shadow_color", text="")
            
            # Emoji Grid
            layout.separator()
            box.label(text="Emojis", icon='HEART')
            col = box.column(align=True)
            
            emojis = ["😀", "😂", "🥰", "😎", "🤔", "👍", "👎", "🔥", "⚠️", "❌", "✅", "🛑"]
            
            # Simple 4x3 grid
            row = col.row(align=True)
            for i, emo in enumerate(emojis):
                op = row.operator("better_image.add_emoji", text=emo)
                op.emoji = emo
                if (i + 1) % 4 == 0 and i < len(emojis) - 1:
                    row = col.row(align=True)
        
        elif props.active_tool == 'CROP':
            box.label(text="Crop Settings", icon='BORDERMOVE')
            box.operator("better_image.apply_crop", text="Apply Crop", icon='CHECKMARK')
            
        elif props.active_tool == 'HIGHLIGHT':
            box.label(text="Highlight Settings", icon='MARKER_HLT')
            box.prop(props, "highlight_color", text="")
            box.prop(props, "highlight_size", text="Size")
            
        elif props.active_tool in {'RECTANGLE', 'ELLIPSE'}:
            box.label(text="Shape Settings", icon='MESH_DATA')
            box.prop(props, "brush_color", text="Color")
            box.prop(props, "brush_size", text="Thickness")
            box.prop(props, "is_filled", text="Fill Shape")
            
        elif props.active_tool == 'ERASER':
            box.label(text="Eraser Settings", icon='BRUSH_DATA')
            box.prop(props, "brush_size", text="Size")
            
        elif props.active_tool == 'PIXELATE':
            box.label(text="Pixelate Settings", icon='NODE_COMPOSITING')
            box.prop(props, "pixelate_size", text="Tile Size")

        else: # Draw, Arrow, None
            box.label(text="Brush Settings", icon='BRUSH_DATA')
            box.prop(props, "brush_color", text="")
            box.prop(props, "brush_size", text="Size")
            if props.active_tool == 'DRAW':
                box.prop(props, "use_stabilizer")
                if props.use_stabilizer:
                    box.prop(props, "stabilizer_factor", slider=True)
        
        # Annotation Actions
        layout.separator()
        row = layout.row(align=True)
        row.operator("better_image.clear_annotations", text="Clear All", icon='X')
        row.operator("better_image.save_annotations", text="Bake All", icon='FILE_TICK')
        
        # Export
        layout.separator()
        box = layout.box()
        box.operator("better_image.copy_to_clipboard", text="Copy to Clipboard", icon='COPYDOWN')


classes = (
    BETTERIMG_UL_layer_list,
    BETTERIMG_PT_main_panel,
    BETTERIMG_PT_layers,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
