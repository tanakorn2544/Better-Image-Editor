# Better Image Editor for Blender

**Better Image Editor** is a powerful Blender addon that transforms the Image Editor into a feature-rich annotation and screenshot tool. It allows you to draw strokes, shapes, arrows, and text directly onto images with a non-destructive, object-based workflow.

## Key Features (v3.0)

### 🎨 Drawing & Annotation
- **Freehand Brush**: Smooth, pressure-sensitive drawing.
- **Shapes**: Easily draw Rectangles, Ellipses, and Arrows.
- **Text & Emojis**: Add text labels and Windows Emojis (🤠🔥✅) directly to your images.
- **Eraser Tool**: Real-time eraser that splits and slices strokes.

### 🛠️ Object-Based Editing
Unlike standard paint tools, everything you draw remains editable!
- **Move Tool**: Select, drag, and reposition any stroke or shape.
- **Edit Properties**: Change text content, color, and size at any time.
- **Non-Destructive**: Your image pixels are safe until you decide to "Bake".

### 📋 Workflow Tools
- **Screen Capture**: One-click capture of the 3D Viewport into the Image Editor.
- **Clipboard Sync**: 
  - **Copy**: Export your annotated image to the system clipboard (Discord/Slack ready!).
  - **Paste**: Paste images from your clipboard directly into Blender.
- **Crop Tool**: Quickly crop images/screenshots to a specific region.

### ⚙️ Advanced System
- **Native Undo/Redo**: Full `Ctrl+Z` support for all actions.
- **Persistence**: Drawings are saved inside your `.blend` file.
- **Layers**: Organize complex annotations into multiple layers (Lock/Hide support).

---

## Installation

1. Download the `betterimageeditor` folder.
2. Place it in your Blender addons directory (e.g., `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`).
3. Open Blender → Preferences → Add-ons.
4. Search for "Better Image Editor" and enable it.

## Usage

The tools are located in the **Image Editor** sidebar (press `N` to toggle).

### 1. Drawing
Select a tool from the grid (Draw, Arrow, Text, etc.) and click/drag on the image canvas.
*   **Draw/Shapes**: Drag to create.
*   **Text/Emoji**: Click to place.

### 2. Editing
Switch to the **Move Tool** (Hand Icon ✋).
*   **Select**: Click any item to select it.
*   **Move**: Drag to reposition.
*   **Resize**: Use the "Size" slider in the sidebar.
*   **Delete**: Press `Del` or click "Delete Selected".

### 3. Layers
Use the **Layers** panel to add new layers or hide existing ones to manage clutter.

### 4. Export
*   **Copy**: Click "Copy to Clipboard" to get a flattened version of your work for sharing.
*   **Bake**: Click "Bake All" to permanently merge drawings into the image pixels.

---

## Shortcuts
- **Right Click / Esc**: Cancel current drawing operation.
- **Ctrl + Z**: Undo.
- **Shift + Ctrl + Z**: Redo.

## Developers
This addon uses a custom GPU-based drawing engine (`gpu` module) and standard `bpy.props` for data persistence. It overrides `LEFTMOUSE` action in the Image Editor via Keymap to support seamless interaction.
