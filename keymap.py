import bpy

addon_keymaps = []

def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
        
        # Bind LEFTMOUSE to our draw tool
        # 'PRESS' means it invokes on click down
        kmi = km.keymap_items.new("better_image.draw_tool", 'LEFTMOUSE', 'PRESS')
        
        addon_keymaps.append((km, kmi))

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
