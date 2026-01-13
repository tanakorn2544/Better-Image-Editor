import bpy
from bpy.props import FloatVectorProperty, IntProperty, EnumProperty, BoolProperty

class BetterImagePoint(bpy.types.PropertyGroup):
    pos: FloatVectorProperty(name="Position", size=2)

class BetterImageStroke(bpy.types.PropertyGroup):
    type: EnumProperty(
        name="Type",
        items=[
            ('STROKE', "Stroke", ""),
            ('RECTANGLE', "Rectangle", ""),
            ('ELLIPSE', "Ellipse", ""),
            ('ARROW', "Arrow", ""),
            ('TEXT', "Text", ""),
            ('CROP', "Crop", ""),
        ],
        default='STROKE'
    )
    # Storing points for freehand stroke
    points: bpy.props.CollectionProperty(type=BetterImagePoint)
    
    # Start/End for Shapes (Vector2)
    start_pos: FloatVectorProperty(name="Start", size=2)
    end_pos: FloatVectorProperty(name="End", size=2)
    
    color: FloatVectorProperty(name="Color", size=4, default=(1,0,0,1))
    size: IntProperty(name="Size", default=5)
    
    text: bpy.props.StringProperty(name="Text Content")
    is_filled: bpy.props.BoolProperty(name="Filled", default=False)
    is_emoji: bpy.props.BoolProperty(name="Is Emoji", default=False)
    layer_id: bpy.props.IntProperty(name="Layer Index", default=0)

class BetterImageLayer(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Layer")
    is_visible: bpy.props.BoolProperty(name="Visible", default=True)
    is_locked: bpy.props.BoolProperty(name="Locked", default=False)

class BetterImageData(bpy.types.PropertyGroup):
    strokes: bpy.props.CollectionProperty(type=BetterImageStroke)
    layers: bpy.props.CollectionProperty(type=BetterImageLayer)
    active_layer_index: IntProperty(default=0)
    
    # Helper to clear
    def clear(self):
        self.strokes.clear()

class BetterImageEditorProperties(bpy.types.PropertyGroup):
    """Properties for Better Image Editor addon"""
    
    brush_color: FloatVectorProperty(
        name="Brush Color",
        subtype='COLOR',
        default=(1.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        description="Color for drawing brush"
    )
    
    brush_size: IntProperty(
        name="Brush Size",
        default=5,
        min=1,
        max=100,
        description="Size of the brush in pixels"
    )
    
    highlight_color: FloatVectorProperty(
        name="Highlight Color",
        subtype='COLOR_GAMMA',
        size=4,
        default=(1.0, 1.0, 0.0, 0.4),
        min=0.0,
        max=1.0,
        description="Color for highlighting (with alpha)"
    )
    
    highlight_size: IntProperty(
        name="Highlight Size",
        default=20,
        min=5,
        max=100,
        description="Size of the highlighter in pixels"
    )
    
    active_tool: EnumProperty(
        name="Active Tool",
        items=[
            ('NONE', "None", "No tool active"),
            ('MOVE', "Move", "Select and move objects"),
            ('DRAW', "Draw", "Freehand drawing tool"),
            ('HIGHLIGHT', "Highlight", "Semi-transparent highlighter"),
            ('ERASER', "Eraser", "Erase parts of strokes"),
            ('ARROW', "Arrow", "Draw an arrow"),
            ('RECTANGLE', "Rectangle", "Draw a rectangle"),
            ('ELLIPSE', "Ellipse", "Draw an ellipse"),
            ('TEXT', "Text", "Add text annotation"),
            ('CROP', "Crop", "Crop image region"),
        ],
        default='NONE',
        description="Currently active drawing tool"
    )
    
    text_content: bpy.props.StringProperty(
        name="Text Content",
        default="Text",
        description="Content for text annotation"
    )
    
    text_size: IntProperty(
        name="Text Size",
        default=24,
        min=8,
        max=200,
        description="Font size for text"
    )
    
    is_filled: BoolProperty(
        name="Fill Shapes",
        default=False,
        description="Whether to fill shapes (Rectangle, Ellipse)"
    )
    
    is_drawing: BoolProperty(
        name="Is Drawing",
        default=False,
        description="Whether drawing mode is active"
    )

    is_recording: BoolProperty(
        name="Is Recording",
        default=False,
        description="Whether GIF recording is active"
    )

    recording_start_time: bpy.props.FloatProperty(
        name="Recording Start Time",
        default=0.0
    )

    # Dynamic getter/setter for editing selected text
    def get_selected_text(self):
        from . import drawing
        idx = drawing.RUNTIME_CACHE['selected_index']
        # Access via Scene Data
        data = bpy.context.scene.better_image_data
        if idx != -1 and idx < len(data.strokes):
             item = data.strokes[idx]
             if item.type == 'TEXT':
                 return item.text
        return ""

    def set_selected_text(self, value):
        from . import drawing
        idx = drawing.RUNTIME_CACHE['selected_index']
        data = bpy.context.scene.better_image_data
        if idx != -1 and idx < len(data.strokes):
             item = data.strokes[idx]
             if item.type == 'TEXT':
                 item.text = value
                 if bpy.context.area: bpy.context.area.tag_redraw()

    selected_text: bpy.props.StringProperty(
        name="Edit Text",
        get=get_selected_text,
        set=set_selected_text,
        description="Edit content of selected text item"
    )

    def get_selected_size(self):
        from . import drawing
        idx = drawing.RUNTIME_CACHE['selected_index']
        data = bpy.context.scene.better_image_data
        if idx != -1 and idx < len(data.strokes):
             item = data.strokes[idx]
             return item.size
        return 5

    def set_selected_size(self, value):
        from . import drawing
        idx = drawing.RUNTIME_CACHE['selected_index']
        data = bpy.context.scene.better_image_data
        if idx != -1 and idx < len(data.strokes):
             item = data.strokes[idx]
             item.size = value
             if bpy.context.area: bpy.context.area.tag_redraw()

    selected_item_size: IntProperty(
        name="Edit Size",
        get=get_selected_size,
        set=set_selected_size,
        min=1, max=300,
        description="Edit size of selected item (Text, Stroke, Shape)"
    )


classes = (
    BetterImagePoint,
    BetterImageStroke,
    BetterImageLayer,
    BetterImageData,
    BetterImageEditorProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.better_image_editor = bpy.props.PointerProperty(
        type=BetterImageEditorProperties
    )
    bpy.types.Scene.better_image_data = bpy.props.PointerProperty(
        type=BetterImageData
    )


def unregister():
    del bpy.types.Scene.better_image_data
    del bpy.types.Scene.better_image_editor
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
