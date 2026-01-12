"""
Operators for betterimageeditor.
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty
from . import clipboard
from . import drawing
from mathutils import Vector

# Reuse previous clipboard operators
class BETTERIMG_OT_capture_screen(Operator):
    bl_idname = "better_image.capture_screen"
    bl_label = "Capture Screen"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            pixels, width, height = clipboard.capture_full_screen()
            image = clipboard.create_blender_image_from_pixels("Screenshot", pixels, width, height)
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = image
                    break
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error: {e}")
            return {'CANCELLED'}

class BETTERIMG_OT_paste_from_clipboard(Operator):
    bl_idname = "better_image.paste_from_clipboard"
    bl_label = "Paste"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            bmp_path = clipboard.get_clipboard_as_temp_bmp()
            if not bmp_path: 
                self.report({'WARNING'}, "No image in clipboard")
                return {'CANCELLED'}
            
            try:
                image = bpy.data.images.load(bmp_path)
                image.name = "Clipboard"
                image.pack() 
            except Exception as e:
                self.report({'ERROR'}, f"Failed to load image: {e}")
                return {'CANCELLED'}
            finally:
                if os.path.exists(bmp_path):
                    try: os.remove(bmp_path)
                    except: pass
            
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR': 
                    area.spaces.active.image = image
            
            return {'FINISHED'}
        except Exception as e: 
            self.report({'ERROR'}, f"Paste Error: {e}")
            return {'CANCELLED'}

class BETTERIMG_OT_copy_to_clipboard(Operator):
    bl_idname = "better_image.copy_to_clipboard"
    bl_label = "Copy"
    bl_options = {'REGISTER'}
    def execute(self, context):
        space = context.space_data
        image = space.image
        if not image: return {'CANCELLED'}
        
        # Non-destructive copy
        result = drawing.get_composed_image_pixels(image)
        if result:
            pixels, w, h = result
            # Pixels are from GPU (0..1 floats usually, unless read() returns ints? 
            # GPUOffScreen.texture_color.read() returns Buffer of floats for RGBA16F/32F
            # Let's check format. We used RGBA16F.
            # So it is floats.
            clipboard.copy_pixels_to_clipboard(pixels, w, h)
            self.report({'INFO'}, "Copied to Clipboard")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to copy")
            return {'CANCELLED'}

class BETTERIMG_OT_draw_tool(Operator):
    """Universal tool invoked by Keymap (Left Click)"""
    bl_idname = "better_image.draw_tool"
    bl_label = "Draw Tool"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'} 
    
    _start_mouse = None
    _start_item_pos = None # For undo/delta calc
    
    def invoke(self, context, event):
        if context.area.type != 'IMAGE_EDITOR': return {'PASS_THROUGH'}
        if context.region.type != 'WINDOW': return {'PASS_THROUGH'}
        
        props = context.scene.better_image_editor
        tool = props.active_tool
        
        if tool == 'NONE': return {'PASS_THROUGH'}
        
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        image_pos = drawing.view_to_image(context, mouse_pos)
        
        # 1. MOVE TOOL
        if tool == 'MOVE':
            idx = drawing.hit_test(context, mouse_pos)
            if idx == -1: 
                return {'PASS_THROUGH'} 
            
            drawing.RUNTIME_CACHE['selected_index'] = idx
            
            # Access PROPERTY object directly
            item = context.scene.better_image_data.strokes[idx]
            self._start_mouse = image_pos
            
            # Store initial state for delta calc
            # Different property names than V2 dict
            if item.type == 'STROKE':
                # Store list of point positions (Vector2)
                self._start_item_pos = [Vector(p.pos) for p in item.points]
            elif item.type == 'TEXT':
                self._start_item_pos = Vector(item.start_pos)
            elif item.type in {'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
                self._start_item_pos = (Vector(item.start_pos), Vector(item.end_pos))
                
            props.is_drawing = True
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
            
        # 2. TEXT TOOL
        elif tool == 'TEXT':
            bpy.ops.better_image.text_popup('INVOKE_DEFAULT', pos_x=image_pos[0], pos_y=image_pos[1])
            return {'FINISHED'}
            
        # 2.5 ERASER
        elif tool == 'ERASER':
             props.is_drawing = True
             context.window_manager.modal_handler_add(self)
             drawing.erase_at(context, image_pos, props.brush_size)
             context.area.tag_redraw()
             return {'RUNNING_MODAL'}
            
        # 3. DRAWING TOOLS
        else:
            props.is_drawing = True
            
            item_type = 'STROKE' if tool in {'DRAW', 'HIGHLIGHT'} else tool
            if tool == 'HIGHLIGHT':
                color = tuple(props.highlight_color)
                size = props.highlight_size
            elif tool == 'DRAW':
                color = (*props.brush_color, 1.0)
                size = props.brush_size
            elif tool == 'CROP':
                color = (1,1,1,1)
                size = 1
            else:
                color = (*props.brush_color, 1.0)
                size = props.brush_size
            
            # Create TRANSIENT DICT for Runtime Cache
            new_item = {'type': item_type, 'color': color, 'size': size}
            
            if item_type == 'STROKE':
                new_item['points'] = [image_pos]
            else:
                new_item['start'] = image_pos
                new_item['end'] = image_pos
                if tool in {'RECTANGLE', 'ELLIPSE'}:
                    new_item['fill'] = props.is_filled
            
            drawing.RUNTIME_CACHE['current_stroke'] = new_item
            
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        props = context.scene.better_image_editor
        tool = props.active_tool
        
        # DRAG UPDATE
        if event.type == 'MOUSEMOVE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            image_pos = drawing.view_to_image(context, mouse_pos)
            
            if tool == 'ERASER':
                 drawing.erase_at(context, image_pos, props.brush_size)
                 context.area.tag_redraw()
                 return {'RUNNING_MODAL'}
            
            if tool == 'MOVE' and self._start_mouse and self._start_item_pos is not None:
                idx = drawing.RUNTIME_CACHE['selected_index']
                # Verify index validity
                if idx >= 0 and idx < len(context.scene.better_image_data.strokes):
                    item = context.scene.better_image_data.strokes[idx]
                    delta_x = image_pos[0] - self._start_mouse[0]
                    delta_y = image_pos[1] - self._start_mouse[1]
                    delta = Vector((delta_x, delta_y))
                    
                    # Direct Property Update
                    if item.type == 'TEXT':
                        item.start_pos = self._start_item_pos + delta
                    elif item.type in {'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
                        s, e = self._start_item_pos
                        item.start_pos = s + delta
                        item.end_pos = e + delta
                    elif item.type == 'STROKE':
                        # Bulk update points?
                        # This loop could be slow for huge strokes, but fine for annotations
                        for i, p_orig in enumerate(self._start_item_pos):
                            if i < len(item.points):
                                item.points[i].pos = p_orig + delta
            
            else:
                # Update Transient Dict
                item = drawing.RUNTIME_CACHE['current_stroke']
                if item:
                    if item['type'] == 'STROKE':
                        item['points'].append(image_pos)
                    elif item['type'] in {'ARROW', 'RECTANGLE', 'ELLIPSE', 'CROP'}:
                        item['end'] = image_pos
                        
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        
        # FINISH
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            props.is_drawing = False
            self._start_mouse = None
            self._start_item_pos = None
            
            item = drawing.RUNTIME_CACHE['current_stroke']
            if item:
                # Validate and Commit
                valid = True
                try:
                    if item['type'] == 'STROKE':
                         if len(item['points']) < 2: valid = False
                    elif item['type'] in {'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
                        start = Vector(item['start'])
                        end = Vector(item['end'])
                        if (start - end).length < 0.1: valid = False
                except:
                    pass

                if valid: 
                    # Commit to Property System
                    drawing.add_stroke_from_runtime(item)
                
            drawing.RUNTIME_CACHE['current_stroke'] = None
            context.area.tag_redraw()
            return {'FINISHED'}
            
        # CANCEL
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            props.is_drawing = False
            
            # Revert Move if active
            if tool == 'MOVE' and self._start_mouse and self._start_item_pos is not None:
                idx = drawing.RUNTIME_CACHE['selected_index']
                data = context.scene.better_image_data
                if idx >= 0 and idx < len(data.strokes):
                     item = data.strokes[idx]
                     # Restore
                     if item.type == 'TEXT':
                         item.start_pos = self._start_item_pos
                     elif item.type in {'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
                         item.start_pos = self._start_item_pos[0]
                         item.end_pos = self._start_item_pos[1]
                     elif item.type == 'STROKE':
                         for i, p_orig in enumerate(self._start_item_pos):
                             if i < len(item.points):
                                 item.points[i].pos = p_orig

            drawing.RUNTIME_CACHE['current_stroke'] = None
            context.area.tag_redraw()
            return {'CANCELLED'}
            
        return {'RUNNING_MODAL'}


class BETTERIMG_OT_add_emoji(Operator):
    """Add an Emoji"""
    bl_idname = "better_image.add_emoji"
    bl_label = "Add Emoji"
    bl_options = {'REGISTER', 'UNDO'}
    emoji: StringProperty()
    def execute(self, context):
        props = context.scene.better_image_editor
        region = context.region
        view_center = (region.width / 2, region.height / 2)
        pos = drawing.view_to_image(context, view_center)
        item = {
            'type': 'TEXT', 'pos': pos, 'text': self.emoji,
            'size': props.text_size * 2, 'color': (1, 1, 1, 1), 'is_emoji': True
        }
        drawing.add_stroke_from_runtime(item)
        props.active_tool = 'MOVE'
        context.area.tag_redraw()
        return {'FINISHED'}

class BETTERIMG_OT_delete_selected(Operator):
    """Delete selected item"""
    bl_idname = "better_image.delete_selected"
    bl_label = "Delete"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        if drawing.delete_selected():
            context.area.tag_redraw()
            return {'FINISHED'}
        return {'CANCELLED'}

class BETTERIMG_OT_apply_crop(Operator):
    bl_idname = "better_image.apply_crop"
    bl_label = "Apply Crop"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        strokes = context.scene.better_image_data.strokes
        # Find crop item via Property iteration
        crop_idx = -1
        crop_item = None
        for i, item in enumerate(strokes):
            if item.type == 'CROP':
                crop_idx = i
                crop_item = item
                break
        
        if not crop_item: return {'CANCELLED'}
        image = context.space_data.image
        if not image: return {'CANCELLED'}
        
        # Access Property Vector
        p1 = crop_item.start_pos
        p2 = crop_item.end_pos
        x_min, x_max = sorted([int(p1[0]), int(p2[0])])
        y_min, y_max = sorted([int(p1[1]), int(p2[1])])
        w, h = image.size
        x_min = max(0, x_min); y_min = max(0, y_min)
        x_max = min(w, x_max); y_max = min(h, y_max)
        nw, nh = x_max - x_min, y_max - y_min
        if nw <= 0 or nh <= 0: return {'CANCELLED'}
        
        old = list(image.pixels[:])
        new_px = [0.0] * (nw * nh * 4)
        for y in range(nh):
            for x in range(nw):
                src_i = ((y_min + y) * w + (x_min + x)) * 4
                dst_i = (y * nw + x) * 4
                new_px[dst_i:dst_i+4] = old[src_i:src_i+4]
        
        image.scale(nw, nh)
        image.pixels = new_px
        
        # Remove Property
        strokes.remove(crop_idx)
        context.area.tag_redraw()
        return {'FINISHED'}

class BETTERIMG_OT_clear_annotations(Operator):
    bl_idname = "better_image.clear_annotations"
    bl_label = "Clear"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        drawing.clear_strokes()
        context.area.tag_redraw()
        return {'FINISHED'}

class BETTERIMG_OT_save_annotations(Operator):
    bl_idname = "better_image.save_annotations"
    bl_label = "Bake"
    bl_options = {'REGISTER', 'UNDO'} 
    def execute(self, context):
        space = context.space_data
        if not space.image: return {'CANCELLED'}
        drawing.bake_strokes_to_image(space.image)
        context.area.tag_redraw()
        return {'FINISHED'}

class BETTERIMG_OT_set_tool(Operator):
    bl_idname = "better_image.set_tool"
    bl_label = "Set Tool"
    tool: StringProperty()
    def execute(self, context):
        context.scene.better_image_editor.active_tool = self.tool
        return {'FINISHED'}
    def invoke(self, context, event):
        context.scene.better_image_editor.active_tool = self.tool
        return {'FINISHED'}

class BETTERIMG_OT_add_layer(Operator):
    bl_idname = "better_image.add_layer"
    bl_label = "Add Layer"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        data = context.scene.better_image_data
        layer = data.layers.add()
        layer.name = f"Layer {len(data.layers)}"
        data.active_layer_index = len(data.layers) - 1
        return {'FINISHED'}

class BETTERIMG_OT_remove_layer(Operator):
    bl_idname = "better_image.remove_layer"
    bl_label = "Remove Layer"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        data = context.scene.better_image_data
        idx = data.active_layer_index
        if 0 <= idx < len(data.layers):
            data.layers.remove(idx)
            if data.active_layer_index >= len(data.layers):
                data.active_layer_index = max(0, len(data.layers) - 1)
            return {'FINISHED'}
        return {'CANCELLED'}

class BETTERIMG_OT_text_popup(Operator):
    bl_idname = "better_image.text_popup"
    bl_label = "Enter Text"
    bl_options = {'REGISTER', 'UNDO'}
    text: StringProperty(name="Content", default="Text")
    pos_x: bpy.props.FloatProperty()
    pos_y: bpy.props.FloatProperty()
    def execute(self, context):
        props = context.scene.better_image_editor
        item = {
            'type': 'TEXT', 'pos': (self.pos_x, self.pos_y),
            'text': self.text, 'size': props.text_size,
            'color': (*props.brush_color, 1.0)
        }
        drawing.add_stroke_from_runtime(item)
        props.active_tool = 'MOVE'
        context.area.tag_redraw()
        return {'FINISHED'}
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

classes = (
    BETTERIMG_OT_capture_screen,
    BETTERIMG_OT_paste_from_clipboard,
    BETTERIMG_OT_copy_to_clipboard,
    BETTERIMG_OT_draw_tool,
    BETTERIMG_OT_add_emoji,
    BETTERIMG_OT_delete_selected,
    BETTERIMG_OT_apply_crop,
    BETTERIMG_OT_clear_annotations,
    BETTERIMG_OT_save_annotations,
    BETTERIMG_OT_set_tool,
    BETTERIMG_OT_add_layer,
    BETTERIMG_OT_remove_layer,
    BETTERIMG_OT_text_popup,
)

def register():
    for cls in classes: bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
