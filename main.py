from flask import Flask, render_template, request, send_file
from rembg import remove
from PIL import Image
import numpy as np
import io
import os
import face_recognition
import cv2  # Import OpenCV

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Define passport photo sizes for different countries in pixels (at 300 DPI)
# Format: 'COUNTRY_KEY': (width_pixels, height_pixels, "display_dimensions")
PASSPORT_SIZES = {
    'india': (413, 531, "35mm x 45mm"),
    'usa': (600, 600, "2in x 2in"),
    'schengen': (413, 531, "35mm x 45mm"),
    'uk': (413, 531, "35mm x 45mm"),
    'canada': (591, 827, "50mm x 70mm"),
    'australia': (413, 531, "35mm x 45mm"),
    'china': (390, 567, "33mm x 48mm"),
    # Add more countries as needed
}


@app.route('/')
def index():
    # Pass the entire PASSPORT_SIZES dictionary to the template
    return render_template('index.html', passport_countries_data=PASSPORT_SIZES)


@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(filepath, mimetype='image/jpeg', as_attachment=True)


@app.route('/process', methods=['POST'])
def process():
    try:
        file = request.files['image']
        bg_color = request.form.get('bg_color', '#ffffff')
        num_copies_option = request.form.get('num_copies', '8')
        country = request.form.get('country', 'india')  # Get selected country, default to 'india'

        if file.filename == '':
            return "No file uploaded", 400

        # Get target dimensions based on selected country
        target_width, target_height, _ = PASSPORT_SIZES.get(country, PASSPORT_SIZES['india'])

        input_data = file.read()
        output_data = remove(input_data)  # This is the RGBA image with background removed

        # Convert the rembg output to a PIL Image
        image_pil = Image.open(io.BytesIO(output_data)).convert("RGBA")

        # --- Enhancement: Refine the Alpha Channel (Mask) using OpenCV ---
        # Convert PIL RGBA image to OpenCV format
        img_cv = np.array(image_pil)
        alpha_channel = img_cv[:, :, 3]  # Extract the alpha channel

        # Apply morphological operations to refine the mask
        # Kernel for erosion/dilation
        kernel = np.ones((3, 3), np.uint8)  # Small kernel for subtle changes

        # Erosion followed by Dilation (Opening) to remove small noise outside the object
        # This can sometimes thin the edges
        mask_opened = cv2.morphologyEx(alpha_channel, cv2.MORPH_OPEN, kernel, iterations=1)

        # Dilation followed by Erosion (Closing) to close small holes inside the object
        # This can sometimes thicken the edges
        mask_closed = cv2.morphologyEx(mask_opened, cv2.MORPH_CLOSE, kernel, iterations=1)

        # You can choose to use mask_closed or experiment with others.
        # For general passport photos, a slight closing often helps fill small gaps.
        refined_alpha = mask_closed

        # Convert the refined alpha back to a PIL Image and put it into the original image
        refined_alpha_pil = Image.fromarray(refined_alpha)
        image_pil.putalpha(refined_alpha_pil)  # Update the alpha channel of the original image

        # Now `image_pil` has the refined background removal

        # Face crop
        img_rgb_for_face = np.array(image_pil.convert("RGB"))
        face_locations = face_recognition.face_locations(img_rgb_for_face)
        width, height = image_pil.size

        if face_locations:
            top, right, bottom, left = face_locations[0]
            face_center_x = (left + right) // 2
            face_height = bottom - top

            # Padding around the face for passport standards
            pad_top = int(face_height * 0.8)
            pad_bottom = int(face_height * 1.0)

            crop_top = max(0, top - pad_top)
            crop_bottom = min(height, bottom + pad_bottom)

            crop_height = crop_bottom - crop_top
            crop_width = int(crop_height * (target_width / target_height))

            crop_left = max(0, face_center_x - crop_width // 2)
            crop_right = crop_left + crop_width

            if crop_right > width:
                crop_right = width
                crop_left = width - crop_width
            if crop_left < 0:
                crop_left = 0
                crop_right = crop_width

            cropped = image_pil.crop((crop_left, crop_top, crop_right, crop_bottom))
        else:
            # If no face detected, just center-crop to target dimensions
            left = (width - target_width) // 2
            top = (height - target_height) // 2
            # Ensure crop dimensions don't exceed original image size
            cropped_left = max(0, left)
            cropped_top = max(0, top)
            cropped_right = min(width, left + target_width)
            cropped_bottom = min(height, top + target_height)
            cropped = image_pil.crop((cropped_left, cropped_top, cropped_right, cropped_bottom))

            # If the image is smaller than target, resize it directly without cropping
            if cropped.size[0] < target_width or cropped.size[1] < target_height:
                resized = image_pil.resize((target_width, target_height), Image.LANCZOS)
            else:
                resized = cropped.resize((target_width, target_height), Image.LANCZOS)

        # Resize the cropped image to target passport photo dimensions
        resized = cropped.resize((target_width, target_height), Image.LANCZOS)

        # Apply background color
        bg = Image.new("RGB", resized.size, bg_color)
        bg.paste(resized, mask=resized.split()[3])

        # Add a thin black border around each passport photo for cutting guides
        bordered = Image.new("RGB", (target_width + 4, target_height + 4), "black")
        bordered.paste(bg, (2, 2))

        # --- Conditional Output: Single Image or Sheet ---
        if num_copies_option == 'single_image':
            output_filename = f'{country}_passport_photo.jpg'
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)
            bordered.save(output_path, quality=90)
            return render_template('result.html', filename=output_filename)
        else:
            try:
                num_copies = int(num_copies_option)
            except ValueError:
                num_copies = 8

            sheet_width, sheet_height = 1800, 1200
            sheet = Image.new("RGB", (sheet_width, sheet_height), "white")

            photo = bordered
            pw, ph = photo.size

            buffer_px = 20
            max_cols = (sheet_width - buffer_px) // (pw + buffer_px)
            max_rows = (sheet_height - buffer_px) // (ph + buffer_px)

            if num_copies <= 4:
                target_cols = num_copies
                target_rows = 1
            elif num_copies <= 8:
                target_cols = 4
                target_rows = (num_copies + target_cols - 1) // target_cols
            else:
                target_cols = max_cols
                target_rows = (num_copies + target_cols - 1) // target_cols

            target_cols = min(target_cols, max_cols)
            target_rows = min(target_rows, max_rows)

            target_cols = max(1, target_cols)
            target_rows = max(1, target_rows)

            total_photos_width = target_cols * pw
            total_photos_height = target_rows * ph

            x_gap = (sheet_width - total_photos_width) // (target_cols + 1)
            y_gap = (sheet_height - total_photos_height) // (target_rows + 1)

            min_spacing = 10
            x_gap = max(min_spacing, x_gap)
            y_gap = max(min_spacing, y_gap)

            placed = 0
            for row in range(target_rows):
                for col in range(target_cols):
                    if placed >= num_copies:
                        break
                    x = x_gap + col * (pw + x_gap)
                    y = y_gap + row * (ph + y_gap)

                    if x + pw <= sheet_width and y + ph <= sheet_height:
                        sheet.paste(photo, (x, y))
                        placed += 1
                if placed >= num_copies:
                    break

            output_filename = f'{country}_passport_4x6_sheet.jpg'
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)
            sheet.save(output_path, quality=90)

            return render_template('result.html', filename=output_filename)

    except Exception as e:
        app.logger.error(f"Error processing image: {str(e)}")
        return f"❌ An error occurred during processing. Please try again. Error details: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)