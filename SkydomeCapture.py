import bpy
import math
import os

# --- Configuration ---
# Output directory relative to the blend file location. Use "//" prefix.
# Example: "//render_output/"
output_dir = "//skydome_output/"
output_filename = "horizontal_strip.png"
# Point from which the views are rendered
camera_location = (0, 0, 0)
# Final image dimensions
resolution_x = 6144
resolution_y = 1024
# Width of each square tile (should match resolution_y)
tile_size = 1024

# --- Helper Functions ---

def setup_camera(scene, location):
    """Ensures a camera exists, sets it active, positions it, and configures FOV."""
    cam_obj = None
    # Check if a camera exists and is the active one
    if scene.camera and scene.camera.type == 'CAMERA':
        cam_obj = scene.camera
    else:
        # Find existing camera or create a new one
        for obj in scene.objects:
            if obj.type == 'CAMERA':
                cam_obj = obj
                break
        if not cam_obj:
            # Create a new camera
            print("Creating a new camera.")
            bpy.ops.object.camera_add(location=(0,0,0))
            cam_obj = bpy.context.object

    # Set the found/created camera as the active scene camera
    scene.camera = cam_obj
    cam_obj.location = location
    # Set camera to perspective, 90 degree FOV for square aspect ratio
    cam_obj.data.type = 'PERSP'
    # Set Field of View to 90 degrees (pi/2 radians)
    cam_obj.data.angle = math.pi / 2.0
    print(f"Using camera: '{cam_obj.name}' at {location}")
    return cam_obj

def set_render_settings(scene, res_x, res_y):
    """Sets resolution and border settings for strip rendering."""
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    # Use border with crop to border enabled so each view only renders in its tile
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    print(f"Set render resolution to {res_x}x{res_y}")
    print("Enabled render border with crop enabled.")

def set_output_path(scene, dir_path, filename):
    """Sets the render output path and ensures the directory exists."""
    # Expand the relative path "//" to an absolute path
    abs_dir_path = bpy.path.abspath(dir_path)
    if not os.path.isdir(abs_dir_path):
        try:
            os.makedirs(abs_dir_path)
            print(f"Created output directory: {abs_dir_path}")
        except OSError as e:
            print(f"Error creating directory {abs_dir_path}: {e}")
            # Fallback to blend file directory if creation fails
            abs_dir_path = bpy.path.abspath("//")


    filepath = os.path.join(abs_dir_path, filename)
    scene.render.filepath = filepath
    # Configure output image settings
    scene.render.image_settings.file_format = 'PNG' # Or 'JPEG', 'TIFF', etc.
    scene.render.image_settings.color_mode = 'RGBA' # Use 'RGB' if alpha is not needed
    scene.render.image_settings.compression = 15 # PNG compression level (0-100)
    print(f"Set output path to: {filepath}")
    return filepath

# --- Main Script ---

def render_horizontal_strip():
    """Main function to render the horizontal strip."""
    print("Starting horizontal strip render script...")
    scene = bpy.context.scene
    render = scene.render

    if not scene:
        print("Error: No active scene found.")
        return

    try:
        # --- Reset and set up compositor nodes (Blender 4.x safe) ---
        scene.use_nodes = True
        tree = scene.node_tree
        while tree.nodes:
            tree.nodes.remove(tree.nodes[0])
        # Set up a simple compositor: Render Layers -> Composite
        render_layers = tree.nodes.new(type='CompositorNodeRLayers')
        render_layers.location = (0, 0)
        composite = tree.nodes.new(type='CompositorNodeComposite')
        composite.location = (300, 0)
        tree.links.new(render_layers.outputs['Image'], composite.inputs['Image'])

        vt = tree.nodes.new(type='CompositorNodeViewTransform')
        vt.location = (600, 0)
        vt.view_transform = 'Standard'    # or 'Raw'
        vt.look           = 'None'
        # link VT → Composite
        tree.links.new(vt.outputs['Image'], composite.inputs['Image'])

        # --- Setup ---
        cam_obj = setup_camera(scene, camera_location)
        set_render_settings(scene, resolution_x, resolution_y)
        output_filepath = set_output_path(scene, output_dir, output_filename)

        # Set a visible world background color (e.g., blue sky)
        if scene.world:
            scene.world.color = (0.1, 0.2, 0.8)
        else:
            world = bpy.data.worlds.new("World")
            scene.world = world
            scene.world.color = (0.1, 0.2, 0.8)
        # Ensure the world background is visible in the render (not transparent)
        scene.render.film_transparent = False

        # --- Define Views ---
        # Order: X+, X-, Y+, Y-, Z+, Z-
        # Rotations are Euler XYZ in radians. Blender Z is Up.
        # Camera points along its local -Z axis.
        num_tiles = resolution_x // tile_size
        if resolution_x % tile_size != 0:
             print(f"Warning: resolution_x ({resolution_x}) is not a multiple of tile_size ({tile_size}).")

        # Render all 6 directions
        directions = [
            {"name": "X+", "rot": (math.pi/2, 0, -math.pi/2)},
            {"name": "X-", "rot": (math.pi/2, 0, math.pi/2)},
            {"name": "Y+", "rot": (math.pi, 0, 0)},
            {"name": "Y-", "rot": (0, 0, 0)},
            {"name": "Z+", "rot": (math.pi/2, 0, 0)},
            {"name": "Z-", "rot": (math.pi/2, 0, math.pi)},
        ]

        output_base, output_ext = os.path.splitext(os.path.basename(output_filepath))

        temp_cameras = []  # Track temporary cameras for cleanup
        temp_files = []    # Track temp image files for compositing
        for view in directions:
            cam_name = f"Camera_{view['name']}"
            # Only use existing camera or create one if none exist in the scene
            cam_obj = None
            for obj in scene.objects:
                if obj.type == 'CAMERA' and obj.name == cam_name:
                    cam_obj = obj
                    break
            created_camera = False
            if not cam_obj:
                bpy.ops.object.camera_add(location=camera_location)
                cam_obj = bpy.context.object
                cam_obj.name = cam_name
                created_camera = True
            cam_obj.location = camera_location
            cam_obj.rotation_mode = 'XYZ'
            cam_obj.rotation_euler = view["rot"]
            cam_obj.data.type = 'PERSP'
            cam_obj.data.angle = math.pi / 2.0

            # Set the current camera for this view
            scene.camera = cam_obj
            bpy.context.view_layer.update()

            # Set render border for the square portion (full image)
            render.border_min_x = 0.0
            render.border_max_x = 1.0
            render.border_min_y = 0.0
            render.border_max_y = 1.0

            # Set output path for this view
            view_filename = f"view_{view['name']}{output_ext}"
            view_filepath = os.path.join(os.path.dirname(output_filepath), view_filename)
            render.filepath = view_filepath
            temp_files.append(view_filepath)

            # Set render resolution to 1024x1024 for this view
            render.resolution_x = tile_size
            render.resolution_y = tile_size

            # Render and save this view
            bpy.ops.render.render(write_still=True)

            # Preview the camera in the 3D Viewport (if available)
            for area in bpy.context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.camera = cam_obj
                            space.region_3d.view_perspective = 'CAMERA'
            # Preview the rendered view image in Blender's image editor
            try:
                # Remove all images with the same filepath to force a reload from disk
                abs_view_filepath = bpy.path.abspath(view_filepath)
                for img in list(bpy.data.images):
                    if bpy.path.abspath(img.filepath) == abs_view_filepath:
                        bpy.data.images.remove(img)
                img = bpy.data.images.load(view_filepath)
                for area in bpy.context.window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        area.spaces.active.image = img
                        if hasattr(area.spaces.active, 'zoom'):
                            area.spaces.active.zoom = (1.0, 1.0)
                        break
            except Exception as e:
                print(f"Could not preview {view_filename}: {e}")

            # Track temporary cameras for deletion
            if created_camera:
                temp_cameras.append(cam_obj)


        # Restore full strip resolution for compositing
        render.resolution_x = resolution_x
        render.resolution_y = resolution_y

        # --- Use compositor nodes to combine the images ---


        def compose_with_nodes(image_paths, output_path, width, height, tile_size):
            scene = bpy.context.scene
            scene.use_nodes = True
            tree = scene.node_tree
            # Remove all nodes for a clean slate (Blender 4.x compatible)
            while tree.nodes:
                tree.nodes.remove(tree.nodes[0])

            comp_node = tree.nodes.new(type='CompositorNodeComposite')
            comp_node.location = (1000, 0)

            prev_node = None
            for i, img_path in enumerate(image_paths):
                img_node = tree.nodes.new(type='CompositorNodeImage')
                # Blender 4.x: always use load, and check for already loaded images by filepath
                img_name = os.path.basename(img_path)
                loaded_img = None
                for img in bpy.data.images:
                    if bpy.path.abspath(img.filepath) == bpy.path.abspath(img_path):
                        loaded_img = img
                        break
                if loaded_img:
                    img_node.image = loaded_img
                else:
                    img_node.image = bpy.data.images.load(img_path)
                img_node.location = (0, -i * 300)

                trans_node = tree.nodes.new(type='CompositorNodeTranslate')
                trans_node.location = (200, -i * 300)
                # Blender 4.x: Translate node uses inputs[0] for Image, [1] for X, [2] for Y
                trans_node.inputs[1].default_value = (i * tile_size) - 2560
                trans_node.inputs[2].default_value = 0
                tree.links.new(img_node.outputs['Image'], trans_node.inputs[0])

                if prev_node is None:
                    prev_node = trans_node
                else:
                    alpha_node = tree.nodes.new(type='CompositorNodeAlphaOver')
                    alpha_node.location = (400 + i * 200, 0)
                    alpha_node.inputs[0].default_value = 1.0  # Fac
                    tree.links.new(prev_node.outputs['Image'], alpha_node.inputs[1])
                    tree.links.new(trans_node.outputs['Image'], alpha_node.inputs[2])
                    prev_node = alpha_node

            tree.links.new(prev_node.outputs['Image'], comp_node.inputs['Image'])

            scene.render.resolution_x = width
            scene.render.resolution_y = height
            scene.render.filepath = output_path
            bpy.ops.render.render(write_still=True)


        print(f"Saving final strip image to {output_filepath} using compositor nodes...")
        compose_with_nodes(temp_files, output_filepath, resolution_x, resolution_y, tile_size)

        # Preview the final output in Blender's image editor
        try:
            abs_final_filepath = bpy.path.abspath(output_filepath)
            for img in list(bpy.data.images):
                if bpy.path.abspath(img.filepath) == abs_final_filepath:
                    bpy.data.images.remove(img)
            final_img = bpy.data.images.load(output_filepath)
            for area in bpy.context.window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = final_img
                    if hasattr(area.spaces.active, 'zoom'):
                        area.spaces.active.zoom = (1.0, 1.0)
                    break
        except Exception as e:
            print(f"Could not preview final output: {e}")

        # Clean up temporary cameras
        for cam in temp_cameras:
            # Remove from scene and data
            try:
                if cam.name in scene.objects:
                    bpy.data.objects.remove(cam, do_unlink=True)
                elif cam in bpy.data.objects:
                    bpy.data.objects.remove(cam, do_unlink=True)
            except Exception as e:
                print(f"Could not remove camera {cam.name}: {e}")

        # Clean up unused images from bpy.data.images
        used_filepaths = set([bpy.path.abspath(f) for f in temp_files] + [bpy.path.abspath(output_filepath)])
        for img in list(bpy.data.images):
            try:
                if img.filepath and bpy.path.abspath(img.filepath) not in used_filepaths:
                    bpy.data.images.remove(img)
            except Exception:
                pass

        print("Render complete and saved successfully.")

    except Exception as e:
        import traceback
        print(f"\n--- An error occurred during script execution ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print("Traceback:")
        traceback.print_exc()
        print("--------------------------------------------------")


    finally:
        print("Script finished.")

# --- Run the main function ---
if __name__ == "__main__":
    render_horizontal_strip()
