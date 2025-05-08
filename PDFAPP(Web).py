# app.py
import os
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import requests  # Add this for downloading fonts
from io import BytesIO
import re

# Get the absolute path to the directory containing this script
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
           template_folder=os.path.join(BASE_DIR, 'templates'),
           static_folder=os.path.join(BASE_DIR, 'static'))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
FONTS_FOLDER = os.path.join(BASE_DIR, 'static', 'fonts')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['FONTS_FOLDER'] = FONTS_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(FONTS_FOLDER, exist_ok=True)

def clean_text(text):
    """Clean and format the extracted text"""
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?;:\'"-]', '', text)
    # Ensure proper spacing after punctuation
    text = re.sub(r'([.,!?;:])', r'\1 ', text)
    # Remove multiple spaces again
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def pdf_to_text(pdf_path):
    """Extract text from PDF with preserved formatting and indentation"""
    pdf_document = fitz.open(pdf_path)
    pages_text = []
    
    for page in pdf_document:
        # Get text blocks with their positions
        blocks = page.get_text("dict")["blocks"]
        page_content = []
        current_paragraph = []
        last_y = None
        
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    line_indent = None
                    
                    for span in line["spans"]:
                        # Get the text and its position
                        text = span["text"]
                        if text.strip():
                            # Get the x position (indentation)
                            if line_indent is None:
                                line_indent = span["bbox"][0]  # Use bbox instead of origin
                            line_text += text
                    
                    if line_text.strip():
                        # Check if this is a new paragraph
                        if last_y is not None:
                            # If there's a significant vertical gap, it's a new paragraph
                            if abs(line["bbox"][1] - last_y) > 20:  # Use bbox instead of origin
                                if current_paragraph:
                                    page_content.append(" ".join(current_paragraph))
                                    current_paragraph = []
                        
                        # Add the line with its indentation
                        if line_indent is not None:
                            # Convert indentation to spaces (approximate)
                            indent_spaces = int(line_indent / 10)  # Adjust this ratio as needed
                            line_text = " " * indent_spaces + line_text
                        
                        current_paragraph.append(line_text)
                        last_y = line["bbox"][1]  # Use bbox instead of origin
        
        # Add the last paragraph
        if current_paragraph:
            page_content.append(" ".join(current_paragraph))
        
        pages_text.append(page_content)
    
    return pages_text

def calculate_text_dimensions(text, font, line_spacing=1.5):
    """Calculate the dimensions needed for the text"""
    lines = text.split('\n')
    max_width = 0
    total_height = 0
    
    for line in lines:
        # Get the size of the line
        bbox = font.getbbox(line)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        
        max_width = max(max_width, line_width)
        total_height += int(line_height * line_spacing)  # Convert to integer
    
    return int(max_width), int(total_height)  # Convert to integer

def download_google_font(font_name):
    """Download a Google Font and save it locally"""
    try:
        # Convert font name to URL format
        font_url_name = font_name.replace(' ', '+')
        # Get the CSS file
        css_url = f"https://fonts.googleapis.com/css2?family={font_url_name}&display=swap"
        response = requests.get(css_url)
        
        if response.status_code == 200:
            # Extract the font file URL from the CSS
            font_file_url = response.text.split('url(')[1].split(')')[0]
            # Download the font file
            font_file = requests.get(font_file_url)
            
            if font_file.status_code == 200:
                font_path = os.path.join(FONTS_FOLDER, f"{font_name}.ttf")
                with open(font_path, 'wb') as f:
                    f.write(font_file.content)
                return font_path
    except Exception as e:
        print(f"Error downloading font {font_name}: {str(e)}")
    return None

def text_to_handwritten_image(text, font_name, output_path, image_width=800, line_height=40, font_size=30, ink_color="#000000"):
    """Convert text to handwritten image with preserved formatting"""
    try:
        # Check if font exists, if not download it
        font_path = os.path.join(FONTS_FOLDER, f"{font_name}.ttf")
        if not os.path.exists(font_path):
            font_path = download_google_font(font_name)
            if not font_path:
                raise Exception(f"Could not download font {font_name}")

        # Load the font
        font = ImageFont.truetype(font_path, font_size)
        
        # Split text into paragraphs
        paragraphs = text.split('\n')
        
        # Calculate dimensions
        max_width = 0
        total_height = 0
        paragraph_heights = []
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # Get the size of the paragraph
                bbox = font.getbbox(paragraph)
                paragraph_width = bbox[2] - bbox[0]
                paragraph_height = bbox[3] - bbox[1]
                
                max_width = max(max_width, paragraph_width)
                paragraph_heights.append(paragraph_height)
                total_height += paragraph_height
        
        # Add padding and paragraph spacing
        padding = 50
        paragraph_spacing = 30
        image_width = max(image_width, max_width + padding * 2)
        image_height = total_height + (len(paragraphs) - 1) * paragraph_spacing + padding * 2
        
        # Create a white background image
        image = Image.new('RGB', (int(image_width), int(image_height)), color='white')
        draw = ImageDraw.Draw(image)
        
        # Draw the text with preserved formatting
        y = padding
        for paragraph in paragraphs:
            if paragraph.strip():
                # Get the size of the current paragraph
                bbox = font.getbbox(paragraph)
                paragraph_height = bbox[3] - bbox[1]
                
                # Draw the paragraph with its original indentation
                draw.text((padding, int(y)), paragraph, font=font, fill=ink_color)
                y += int(paragraph_height + paragraph_spacing)
        
        # Save the image with high quality
        image.save(output_path, quality=95, optimize=True)
        
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        raise

# Add this new function to get available fonts
def get_available_fonts():
    fonts = []
    for font_file in os.listdir(FONTS_FOLDER):
        if font_file.endswith('.ttf'):
            font_path = os.path.join(FONTS_FOLDER, font_file)
            try:
                # Create a preview image for the font
                preview_path = os.path.join('static', 'font_previews', f"{os.path.splitext(font_file)[0]}.png")
                if not os.path.exists(os.path.dirname(preview_path)):
                    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
                
                # Generate preview if it doesn't exist
                if not os.path.exists(preview_path):
                    generate_font_preview(font_path, preview_path)
                
                fonts.append({
                    'name': os.path.splitext(font_file)[0],
                    'file': font_file,
                    'preview': preview_path
                })
            except Exception as e:
                print(f"Error processing font {font_file}: {str(e)}")
    return fonts

def generate_font_preview(font_path, output_path, text="The quick brown fox jumps over the lazy dog"):
    try:
        # Create a white background image
        img = Image.new('RGB', (800, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # Load the font
        font = ImageFont.truetype(font_path, 40)
        
        # Draw the text
        draw.text((20, 20), text, font=font, fill='black')
        
        # Save the preview
        img.save(output_path)
    except Exception as e:
        print(f"Error generating preview for {font_path}: {str(e)}")

@app.route('/fonts')
def font_selector():
    fonts = get_available_fonts()
    return render_template('font_selector.html', fonts=fonts)

def combine_images_to_pdf(image_paths, output_pdf_path):
    """Combine multiple images into a single PDF file"""
    try:
        # Convert all images to RGB mode and create a list
        images = []
        for img_path in image_paths:
            img = Image.open(img_path)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            images.append(img)
        
        # Save the first image as PDF
        if images:
            images[0].save(
                output_pdf_path,
                save_all=True,
                append_images=images[1:],
                resolution=100.0
            )
        return True
    except Exception as e:
        print(f"Error combining images to PDF: {str(e)}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            pdf_file = request.files['pdf']
            font_name = request.form.get('font')
            font_size = int(request.form.get('fontSize', 30))
            ink_color = request.form.get('inkColor', '#000000')
            
            if pdf_file and font_name:
                pdf_filename = secure_filename(pdf_file.filename)
                pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                pdf_file.save(pdf_path)

                # Get text from PDF with preserved formatting
                pages_text = pdf_to_text(pdf_path)
                image_paths = []
                output_files = []

                # Generate images for each page
                for i, page_paragraphs in enumerate(pages_text):
                    # Join paragraphs with proper spacing
                    page_text = '\n'.join(page_paragraphs)
                    
                    image_path = os.path.join(OUTPUT_FOLDER, f"handwritten_page_{i + 1}.png")
                    text_to_handwritten_image(
                        page_text, 
                        font_name, 
                        image_path,
                        font_size=font_size,
                        ink_color=ink_color
                    )
                    image_paths.append(image_path)
                    output_files.append(f"/download/{os.path.basename(image_path)}")

                # Combine images into a single PDF
                output_pdf_path = os.path.join(OUTPUT_FOLDER, "handwritten_document.pdf")
                if combine_images_to_pdf(image_paths, output_pdf_path):
                    output_files.append(f"/download/handwritten_document.pdf")

                return render_template('success.html', files=output_files)
        
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
