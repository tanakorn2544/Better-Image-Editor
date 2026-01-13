import bpy
import os
import time
import tempfile
import shutil
import struct
from . import clipboard
from . import simple_gif

def write_bmp(path, pixels, width, height):
    """Write raw RGBA bytes to a BMP file."""
    # BMP requires BGRA. Swapping needed if source is RGBA.
    # clipboard.get_screen_region returns RGBA.
    # Fast swap using slicing if possible, but raw loop is slow.
    # However, for 10fps, it might be okay.
    # Optimization: Use bytearray slicing
    
    # Check if we can use a faster method?
    # For now, simplistic swap.
    data = bytearray(pixels)
    # B <-> R
    # p[0] is R, p[2] is B.
    # Bulk swap?
    # No efficient bulk swap in pure python without numpy.
    # Looping...
    for i in range(0, len(data), 4):
         data[i], data[i+2] = data[i+2], data[i]

    file_size = 14 + 40 + len(data)
    offset = 54
    fh = struct.pack('<2sIHH I', b'BM', file_size, 0, 0, offset)
    ih = struct.pack('<IiiHH IIIIII', 40, width, -height, 1, 32, 0, len(data), 0, 0, 0, 0)
    
    with open(path, 'wb') as f:
        f.write(fh); f.write(ih); f.write(data)

class BETTERIMG_OT_record_gif(bpy.types.Operator):
    bl_idname = "better_image.record_gif"
    bl_label = "Record GIF"
    bl_description = "Record the Image Editor area"
    
    _timer = None
    _temp_dir = None
    _frame_count = 0
    
    def invoke(self, context, event):
        props = context.scene.better_image_editor
        if props.is_recording:
             self.stop_recording(context)
             return {'FINISHED'}
        else:
             return self.start_recording(context)

    def start_recording(self, context):
        props = context.scene.better_image_editor
        props.is_recording = True
        props.recording_start_time = time.time()
        
        self._temp_dir = tempfile.mkdtemp(prefix="blender_rec_")
        self._frame_count = 0
        
        # Find Image Editor Area WINDOW region (the canvas)
        self._region = None
        for region in context.area.regions:
            if region.type == 'WINDOW':
                self._region = region
                break
        
        # Fallback if somehow WINDOW not found (unlikely in Image Editor)
        if not self._region:
             self._region = context.region # Use current region as backup
             self.report({'WARNING'}, "Could not find Image Canvas, recording current panel instead.")
        
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window) # 10 FPS
        context.window_manager.modal_handler_add(self)
        
        self.report({'INFO'}, "Recording started...")
        return {'RUNNING_MODAL'}
    
    # ... (stop_recording, load_sequence, modal, capture_frame remain same, just ensure region is used correctly) ...
    # Wait, existing capture_frame uses self._region. Update start_recording is enough.
    # But I should check if capture_frame needs update?
    # capture_frame: x = int(win_x + reg_x).
    # If using WINDOW region, offsets should be correct relative to window.
    
    # ... (rest of BETTERIMG_OT_record_gif) ...

    def stop_recording(self, context):
        props = context.scene.better_image_editor
        props.is_recording = False
        
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            
        self.report({'INFO'}, f"Recording stopped. captured {self._frame_count} frames.")
        
        if self._frame_count > 0:
            self.load_sequence(context)
            # We don't delete temp dir immediately now, as it's used for playback/export
            # Store temp dir in scene props if we want persistence?
            # Or just rely on loaded image.
            # Ideally cleaning up old temp dirs at startup.
            
    def load_sequence(self, context):
        # Load the captured BMPs as an image sequence
        try:
            # 1. Check if an image block already exists
            img = None
            if context.space_data and context.space_data.image:
                img = context.space_data.image
                # If it's already a sequence, maybe reuse? Or create new.
            
            # Create new image block for recording
            img_name = "Screen Recording"
            if img_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[img_name])
            
            # file list
            # We don't need to manually pass files list if they are numbered correctly and we load the first one.
            # But bpy.data.images.load only loads one file.
            # We usually need to set source to SEQUENCE.
            
            filepath = os.path.join(self._temp_dir, "frame_00000.bmp")
            
            img = bpy.data.images.load(filepath, check_existing=False)
            img.name = img_name
            img.source = 'SEQUENCE'
            
            # Use 'filepath' implies the directory scan for sequence.
            
            # Set to space
            if context.space_data.type == 'IMAGE_EDITOR':
                context.space_data.image = img
                # Set Image User to auto refresh and correct length
                # ImageUser is on the space data, not the image itself (for editors)
                # Or for the image block if used in nodes.
                
                # Update Space ImageUser
                iuser = context.space_data.image_user
                iuser.frame_duration = self._frame_count
                iuser.frame_start = 1
                iuser.frame_offset = 0
                iuser.use_auto_refresh = True
                iuser.use_cyclic = True
                
            self.report({'INFO'}, "Sequence Loaded. Press Space to Play.")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load sequence: {e}")

    def modal(self, context, event):
        props = context.scene.better_image_editor
        if not props.is_recording:
            self.stop_recording(context)
            return {'FINISHED'}
        if event.type == 'TIMER':
            self.capture_frame(context)
        return {'PASS_THROUGH'}

    def capture_frame(self, context):
        win_x = context.window.x; win_y = context.window.y
        reg_x = self._region.x; reg_y = self._region.y
        width = self._region.width; height = self._region.height
        
        x = int(win_x + reg_x); y = int(win_y + reg_y)
        w = int(width); h = int(height)
        
        try:
            pixels, cap_w, cap_h = clipboard.get_screen_region(x, y, w, h)
            filename = f"frame_{self._frame_count:05d}.bmp"
            path = os.path.join(self._temp_dir, filename)
            write_bmp(path, pixels, cap_w, cap_h)
            self._frame_count += 1
        except Exception as e:
            print(f"Capture failed: {e}")

class BETTERIMG_OT_open_export_folder(bpy.types.Operator):
    bl_idname = "better_image.open_export_folder"
    bl_label = "Open Folder"
    bl_description = "Open the folder where GIF was saved"
    
    def execute(self, context):
        home = os.path.expanduser("~")
        desktop = os.path.join(home, "Desktop")
        if os.path.exists(desktop):
            os.startfile(desktop)
            self.report({'INFO'}, f"Opened {desktop}")
        else:
            self.report({'WARNING'}, "Desktop folder not found")
        return {'FINISHED'}

class BETTERIMG_OT_export_gif(bpy.types.Operator):
    bl_idname = "better_image.export_gif"
    bl_label = "Export GIF"
    bl_description = "Export current recording to GIF"
    
    def execute(self, context):
        # Find the recording sequence
        img = context.space_data.image
        if not img or img.source != 'SEQUENCE':
            self.report({'WARNING'}, "No recording sequence found")
            return {'CANCELLED'}
        
        filepath = img.filepath
        dirname = os.path.dirname(filepath) # This should be our temp dir
        
        # Validate logic: check if frames exist
        if not os.path.exists(dirname): 
            self.report({'ERROR'}, "Source files missing")
            return {'CANCELLED'}
            
        # Output
        home = os.path.expanduser("~")
        desktop = os.path.join(home, "Desktop")
        timestamp = int(time.time())
        output_file = os.path.join(desktop, f"recording_{timestamp}.gif")
        
        # Count frames
        # Assuming frame_00000.bmp etc
        # We can iterate until file missing
        frames = []
        i = 0
        while True:
            fname = f"frame_{i:05d}.bmp"
            fpath = os.path.join(dirname, fname)
            if not os.path.exists(fpath): break
            frames.append(fpath)
            i += 1
            
        if not frames: return {'CANCELLED'}
        
        # Use Simple GIF (Optimized)
        try:
            # Check first frame dims
            with open(frames[0], 'rb') as f:
                f.seek(18)
                w = struct.unpack('<I', f.read(4))[0]
                h = struct.unpack('<i', f.read(4))[0]
                h = abs(h)
            
            encoder = simple_gif.GIFEncoder(w, h, loop=0)
            encoder.start()
            
            # read pixels from BMP
            # Skip header 54 bytes
            for fpath in frames:
                with open(fpath, 'rb') as f:
                    f.seek(54)
                    pixels = f.read()
                    # Pixels are BGRA in BMP.
                    # Encoder expects RGB/RGBA?
                    # simple_gif expects RGB/RGBA.
                    # We need to swap back or teach simple_gif to handle BGRA.
                    # Updating simple_gif is better.
                    encoder.add_frame(pixels, w, h, delay=10, is_bgra=True)
            
            encoder.finish(output_file)
            self.report({'INFO'}, f"Exported to {output_file}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(BETTERIMG_OT_record_gif)
    bpy.utils.register_class(BETTERIMG_OT_export_gif)
    bpy.utils.register_class(BETTERIMG_OT_open_export_folder)

def unregister():
    bpy.utils.unregister_class(BETTERIMG_OT_record_gif)
    bpy.utils.unregister_class(BETTERIMG_OT_export_gif)
    bpy.utils.unregister_class(BETTERIMG_OT_open_export_folder)
