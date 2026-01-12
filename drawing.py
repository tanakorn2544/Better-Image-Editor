"""
GPU-based drawing system for Better Image Editor.
Handles stroke rendering, shapes, text, baking, and object interaction.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
import blf
import math
import os

# Global runtime state for interaction (selection index is now local to this runtime, or could be property?)
# Let's keep selection runtime for now, or move to properties?
# Moving selection to properties allows "Selected State" to be saved, which is nice.
# But "Current Stroke" is transient during modal.

RUNTIME_CACHE = {
    'current_stroke': None, # Current active action (being drawn)
    'selected_index': -1, # Index of currently selected item
}

# Draw handler reference
_draw_handler = None
_emoji_font_id = 99  # ID for emoji font

# Load Windows Emoji Font
def load_emoji_font():
    font_path = "C:/Windows/Fonts/seguiemj.ttf"
    if os.path.exists(font_path):
        try:
            blf.load(_emoji_font_id, font_path)
            return True
        except:
            # Silently fail if font cannot be loaded
            pass
    return False

# Initialize font on load
try:
    load_emoji_font()
except:
    pass

def get_shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')

def draw_circle(center, radius, color, segments=32, fill=False):
    """Draw a circle using GPU batch."""
    points = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = center[0] + math.cos(angle) * radius
        y = center[1] + math.sin(angle) * radius
        points.append((x, y))
    
    shader = get_shader()
    shader.bind()
    shader.uniform_float("color", color)
    
    mode = 'TRI_FAN' if fill else 'LINE_STRIP'
    if fill:
        points.insert(0, center)
        
    batch = batch_for_shader(shader, mode, {"pos": points})
    batch.draw(shader)


def draw_rect(start, end, color, fill=False):
    """Draw a rectangle."""
    x1, y1 = start
    x2, y2 = end
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    
    shader = get_shader()
    shader.bind()
    shader.uniform_float("color", color)
    
    if fill:
        indices = [(0, 1, 2), (0, 2, 3)]
        fill_points = points[:-1]
        batch = batch_for_shader(shader, 'TRIS', {"pos": fill_points}, indices=indices)
    else:
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    batch.draw(shader)


def draw_arrow(start, end, color, size):
    """Draw an arrow."""
    shader = get_shader()
    shader.bind()
    shader.uniform_float("color", color)
    
    batch = batch_for_shader(shader, 'LINES', {"pos": [start, end]})
    batch.draw(shader)
    
    v_vec = Vector(end) - Vector(start)
    if v_vec.length < 0.1: return
    v_vec.normalize()
    p_vec = Vector((-v_vec.y, v_vec.x))
    
    head_size = size * 3
    p1 = Vector(end) - v_vec * head_size + p_vec * (head_size * 0.5)
    p2 = Vector(end) - v_vec * head_size - p_vec * (head_size * 0.5)
    
    batch = batch_for_shader(shader, 'TRIS', {"pos": [tuple(end), tuple(p1), tuple(p2)]})
    batch.draw(shader)


def draw_text(position, text, size, color, is_emoji=False):
    """Draw text using blf."""
    fid = _emoji_font_id if is_emoji else 0
    blf.position(fid, position[0], position[1], 0)
    blf.size(fid, size)
    blf.color(fid, color[0], color[1], color[2], color[3])
    blf.draw(fid, text)


def hit_test(context, mouse_pos):
    """Check if mouse hits an item. Returns index or -1."""
    # Convert mouse to image space
    image_pos = view_to_image(context, mouse_pos)
    idx_hit = -1
    
    # Access strokes from Scene Data
    if not hasattr(context.scene, 'better_image_data'): return -1
    strokes = context.scene.better_image_data.strokes
    
    # Iterate backwards (top items first)
    for i in range(len(strokes) - 1, -1, -1):
        item = strokes[i]
        itype = item.type
        
        hit = False
        if itype == 'TEXT':
            x, y = item.start_pos
            size = item.size
            w = len(item.text) * size * 0.6
            h = size
            if x <= image_pos[0] <= x + w and y <= image_pos[1] <= y + h:
                hit = True
                
        elif itype in {'RECTANGLE', 'ELLIPSE', 'ARROW'}:
             p1 = Vector(item.start_pos)
             p2 = Vector(item.end_pos)
             min_x = min(p1.x, p2.x) - 5
             max_x = max(p1.x, p2.x) + 5
             min_y = min(p1.y, p2.y) - 5
             max_y = max(p1.y, p2.y) + 5
             if min_x <= image_pos[0] <= max_x and min_y <= image_pos[1] <= max_y:
                 hit = True
                 
        elif itype == 'STROKE':
            if len(item.points) == 0: continue
            # Check bounding box first
            # Optimization: could cache bounds
            xs = [p.pos[0] for p in item.points]
            ys = [p.pos[1] for p in item.points]
            if not xs: continue
            
            min_x = min(xs) - 10
            max_x = max(xs) + 10
            min_y = min(ys) - 10
            max_y = max(ys) + 10
            
            if min_x <= image_pos[0] <= max_x and min_y <= image_pos[1] <= max_y:
                hit = True
                
        if hit:
            idx_hit = i
            break
            
    return idx_hit


def draw_callback():
    """Main draw handler."""
    context = bpy.context
    if not context.area or context.area.type != 'IMAGE_EDITOR': return
    if not context.space_data or not context.space_data.image: return
    
    # Use global data
    if not hasattr(context.scene, 'better_image_data'): return
    strokes = context.scene.better_image_data.strokes
    
    gpu.state.blend_set('ALPHA')
    def to_view(p): return image_to_view(context, p)
    
    # Draw Persistent Strokes
    # Cache layer visibility
    data = context.scene.better_image_data
    layer_vis = {}
    for i, lyr in enumerate(data.layers):
        layer_vis[i] = lyr.is_visible
        
    for idx, item in enumerate(strokes):
        # Check Visibility
        lid = item.layer_id
        if lid in layer_vis and not layer_vis[lid]:
            continue

        itype = item.type
        color = item.color
        size = item.size
        is_emoji = item.is_emoji
        
        is_selected = (idx == RUNTIME_CACHE['selected_index'])
        
        gpu.state.line_width_set(size if itype == 'STROKE' else float(size/2))
        
        draw_color = color
        
        if itype == 'STROKE':
            points = [to_view(p.pos) for p in item.points]
            if len(points) < 2: continue
            shader = get_shader()
            shader.bind()
            shader.uniform_float("color", draw_color)
            batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
            batch.draw(shader)
            
        elif itype == 'ARROW':
            start = to_view(item.start_pos)
            end = to_view(item.end_pos)
            draw_arrow(start, end, draw_color, size)
            
        elif itype == 'RECTANGLE':
            start = to_view(item.start_pos)
            end = to_view(item.end_pos)
            draw_rect(start, end, draw_color, item.is_filled)
            
        elif itype == 'ELLIPSE':
            start = Vector(to_view(item.start_pos))
            end = Vector(to_view(item.end_pos))
            center = (start + end) / 2
            radius = (start - end).length / 2
            draw_circle(center, radius, draw_color, fill=item.is_filled)
            
        elif itype == 'TEXT':
            pos = to_view(item.start_pos)
            draw_text(pos, item.text, item.size, draw_color, is_emoji=is_emoji)
            
        elif itype == 'CROP':
            start = to_view(item.start_pos)
            end = to_view(item.end_pos)
            draw_rect(start, end, (1, 1, 1, 0.5), False)
            
        # Selection Indicator
        if is_selected:
             gpu.state.line_width_set(2.0)
             if itype == 'STROKE' and len(item.points) > 0:
                 pt = to_view(item.points[0].pos)
                 draw_circle(pt, 5, (0, 1, 1, 1))
             elif itype in {'TEXT', 'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
                 pt = to_view(item.start_pos)
                 draw_circle(pt, 5, (0, 1, 1, 1))

    # Draw Transient Stroke (Current Drawing - not yet committed to props)
    curr = RUNTIME_CACHE['current_stroke']
    if curr:
        itype = curr['type']
        color = curr['color']
        size = curr['size']
        gpu.state.line_width_set(size if itype == 'STROKE' else float(size/2))
        
        if itype == 'STROKE':
             points = [to_view(p) for p in curr['points']]
             if len(points) > 1:
                 shader = get_shader()
                 shader.bind()
                 shader.uniform_float("color", color)
                 batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
                 batch.draw(shader)
        elif itype in {'RECTANGLE', 'ELLIPSE', 'ARROW', 'CROP'}:
             start = to_view(curr['start'])
             end = to_view(curr['end'])
             if itype == 'RECTANGLE': draw_rect(start, end, color, curr.get('fill', False))
             elif itype == 'ELLIPSE': 
                 s = Vector(start); e = Vector(end); 
                 c = (s+e)/2; r = (s-e).length/2
                 draw_circle(c, r, color, fill=curr.get('fill', False))
             elif itype == 'ARROW': draw_arrow(start, end, color, size)
             elif itype == 'CROP': draw_rect(start, end, (1,1,1,0.5), False)

    gpu.state.blend_set('NONE')
    gpu.state.line_width_set(1.0)

def image_to_view(context, image_coord):
    """Convert image space (pixels) to region space (screen pixels)."""
    if not context.region or not context.region.view2d: return (0, 0)
    try:
        icon_x, icon_y = context.region.view2d.view_to_region(image_coord[0], image_coord[1], clip=False)
        return (icon_x, icon_y)
    except:
        return (0, 0)

def view_to_image(context, view_coord):
    """Convert region space (screen pixels) to image space (pixels)."""
    if not context.region or not context.region.view2d: return (0, 0)
    try:
        img_x, img_y = context.region.view2d.region_to_view(view_coord[0], view_coord[1])
        return (img_x, img_y)
    except:
        return (0, 0)

def bake_stroke_to_offscreen(offscreen, image):
    strokes = bpy.context.scene.better_image_data.strokes
    w, h = image.size
    with offscreen.bind():
        try:
            with gpu.matrix.push_pop():
                gpu.matrix.load_identity()
                ortho_matrix = Matrix.Identity(4)
                ortho_matrix[0][0] = 2.0 / w
                ortho_matrix[1][1] = 2.0 / h
                ortho_matrix[0][3] = -1.0
                ortho_matrix[1][3] = -1.0
                gpu.matrix.load_projection_matrix(ortho_matrix)
                
                gpu.state.blend_set('NONE')
                try:
                    if image.bindcode == 0: image.gl_load()
                    shader = gpu.shader.from_builtin('IMAGE_2D_COLOR')
                    shader.bind()
                    shader.uniform_image("image", image)
                    shader.uniform_float("color", (1, 1, 1, 1))
                    points = [(0, 0), (w, 0), (w, h), (0, h)]
                    tex_co = [(0, 0), (1, 0), (1, 1), (0, 1)]
                    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": points, "texCoord": tex_co})
                    batch.draw(shader)
                except Exception as e: print(f"Error drawing image: {e}")
                
                gpu.state.blend_set('ALPHA')
                # Iterate Scene Data
                for item in strokes:
                    itype = item.type
                    color = item.color
                    size = item.size
                    gpu.state.line_width_set(size if itype == 'STROKE' else float(size/2))
                    
                    if itype == 'STROKE':
                        points = [p.pos for p in item.points] 
                        if len(points) < 2: continue
                        shader = get_shader()
                        shader.bind()
                        shader.uniform_float("color", color)
                        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
                        batch.draw(shader)
                    elif itype == 'ARROW':
                        draw_arrow(item.start_pos, item.end_pos, color, size)
                    elif itype == 'RECTANGLE':
                        draw_rect(item.start_pos, item.end_pos, color, item.is_filled)
                    elif itype == 'ELLIPSE':
                        start = Vector(item.start_pos)
                        end = Vector(item.end_pos)
                        center = (start + end) / 2
                        radius = (start - end).length / 2
                        draw_circle(center, radius, color, fill=item.is_filled)
                    elif itype == 'TEXT':
                        draw_text(item.start_pos, item.text, item.size, color, item.is_emoji)
                gpu.state.blend_set('NONE')
        except Exception as e:
            print(f"Bake Error: {e}")

def bake_strokes_to_image(image):
    strokes = bpy.context.scene.better_image_data.strokes
    if len(strokes) == 0: return False
    
    width, height = image.size
    try: 
        offscreen = gpu.types.GPUOffScreen(width, height, format='RGBA16F')
    except: return False
    
    bake_stroke_to_offscreen(offscreen, image)
    
    try:
        buffer = offscreen.texture_color.read()
        image.pixels.foreach_set(buffer)
    except Exception as e:
        print(f"Read Error: {e}")
        return False
        
    bpy.context.scene.better_image_data.strokes.clear()
    return True

def clear_strokes():
    bpy.context.scene.better_image_data.strokes.clear()
    RUNTIME_CACHE['current_stroke'] = None
    RUNTIME_CACHE['selected_index'] = -1

# Add item logic is now handled by Operators creating properties directly.
# But we might need a helper:
def add_stroke_from_runtime(stroke_dict):
    """Commit a runtime stroke dict to Scene Data."""
    data = bpy.context.scene.better_image_data
    strokes = data.strokes
    item = strokes.add()
    item.type = stroke_dict['type']
    item.color = stroke_dict['color']
    item.size = int(stroke_dict['size'])
    # Assign Layer
    item.layer_id = data.active_layer_index
    
    if 'text' in stroke_dict: item.text = stroke_dict['text']
    if 'is_emoji' in stroke_dict: item.is_emoji = stroke_dict['is_emoji']
    if 'fill' in stroke_dict: item.is_filled = stroke_dict['fill']
    
    # Coordinates
    if 'start' in stroke_dict: item.start_pos = stroke_dict['start']
    if 'end' in stroke_dict: item.end_pos = stroke_dict['end']
    if 'pos' in stroke_dict: item.start_pos = stroke_dict['pos'] # Map 'pos' to 'start_pos' for TEXT
    
    if 'points' in stroke_dict:
        pts = stroke_dict['points']
        for p in pts:
            new_pt = item.points.add()
            new_pt.pos = p
            
    RUNTIME_CACHE['selected_index'] = len(strokes) - 1

def get_composed_image_pixels(image):
    """
    Return pixels of Image + Annotations without modifying the original.
    Returns (pixels, width, height) or None.
    """
    strokes = bpy.context.scene.better_image_data.strokes
    width, height = image.size
    
    try: 
        offscreen = gpu.types.GPUOffScreen(width, height, format='RGBA16F')
    except: return None
    
    # Reuse the bake logic but don't clear strokes
    bake_stroke_to_offscreen(offscreen, image)
    
    try:
        buffer = offscreen.texture_color.read()
        return buffer.to_list(), width, height
    except Exception as e:
        print(f"Read Error: {e}")
        return None

def delete_selected():
    idx = RUNTIME_CACHE['selected_index']
    strokes = bpy.context.scene.better_image_data.strokes
    if idx != -1 and idx < len(strokes):
        strokes.remove(idx)
        RUNTIME_CACHE['selected_index'] = -1
        return True
    return False

def erase_at(context, position, radius):
    """Erase parts of strokes at position."""
    data = context.scene.better_image_data
    strokes = data.strokes
    
    # Iterate backwards to safely remove/split
    for s_idx in range(len(strokes)-1, -1, -1):
        stroke = strokes[s_idx]
        
        # Skip locked/hidden layers?
        # Check Layer Visibility
        layer_idx = stroke.layer_id
        if layer_idx < len(data.layers):
            if not data.layers[layer_idx].is_visible or data.layers[layer_idx].is_locked:
                continue
        
        if stroke.type != 'STROKE':
             # For Shapes, erase if center hit? or edges?
             # Simple logic: Bounding Box hit = Delete Object
             # Check bounds
             p1 = Vector(stroke.start_pos)
             p2 = Vector(stroke.start_pos) # Text has only start
             if hasattr(stroke, 'end_pos') and stroke.type not in {'TEXT'}:
                 p2 = Vector(stroke.end_pos)
             
             # Distance to bounding box?
             # Simple: If click inside, delete.
             # Use Hit Test logic?
             pass # For V1, Eraser only works on STROKES (Lines). Use Delete Selected for shapes.
             continue
        
        # STROKE: Check points
        points_to_remove = set()
        
        # Optimization: Bounding Box check first
        # ...
        
        for p_idx, p in enumerate(stroke.points):
            dist = (Vector(p.pos) - Vector(position)).length
            if dist < radius:
                points_to_remove.add(p_idx)
        
        if not points_to_remove: continue
        
        # Rebuild segments - CRITICAL SAFETY: Copy to Vector to detach from blender memory
        original_points = [Vector(p.pos) for p in stroke.points]
        segments = []
        current_segment = []
        for i, pos in enumerate(original_points):
            if i in points_to_remove:
                if len(current_segment) > 0:
                    segments.append(current_segment)
                    current_segment = []
            else:
                current_segment.append(pos)
        if len(current_segment) > 0: segments.append(current_segment)
        
        # Apply changes
        if not segments:
            strokes.remove(s_idx)
        else:
            # Replace current stroke with Segment 0
            stroke.points.clear()
            for p in segments[0]:
                np = stroke.points.add()
                np.pos = p
            
            # Create new strokes for other segments
            for seg in segments[1:]:
                # Check min length? 1 point strokes are invisible
                if len(seg) < 2: continue
                
                new_s = strokes.add()
                new_s.type = stroke.type
                new_s.color = stroke.color
                new_s.size = stroke.size
                new_s.layer_id = stroke.layer_id
                for p in seg:
                    np = new_s.points.add()
                    np.pos = p

def register():
    global _draw_handler
    _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(draw_callback, (), 'WINDOW', 'POST_PIXEL')

def unregister():
    global _draw_handler
    if _draw_handler:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
