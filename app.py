# app.py
import os
import re
import uuid
import logging
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, jsonify, Response
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Get the absolute path to the directory containing this script
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
FONTS_FOLDER = os.path.join(BASE_DIR, 'static', 'fonts')
FONT_PREVIEWS_FOLDER = os.path.join(BASE_DIR, 'static', 'font_previews')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['FONTS_FOLDER'] = FONTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = os.environ.get("SESSION_SECRET", "default_secret_key")

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(FONTS_FOLDER, exist_ok=True)
os.makedirs(FONT_PREVIEWS_FOLDER, exist_ok=True)

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
                                line_indent = span["bbox"][0]
                            line_text += text
                    
                    if line_text.strip():
                        # Check if this is a new paragraph
                        if last_y is not None:
                            # If there's a significant vertical gap, it's a new paragraph
                            if abs(line["bbox"][1] - last_y) > 20:
                                if current_paragraph:
                                    page_content.append(" ".join(current_paragraph))
                                    current_paragraph = []
                        
                        # Add the line with its indentation
                        if line_indent is not None:
                            # Convert indentation to spaces (approximate)
                            indent_spaces = int(line_indent / 10)  # Adjust this ratio as needed
                            line_text = " " * indent_spaces + line_text
                        
                        current_paragraph.append(line_text)
                        last_y = line["bbox"][1]
        
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
        app.logger.error(f"Error downloading font {font_name}: {str(e)}")
    return None

def text_to_handwritten_image(text, font_name, output_path, image_width=800, line_height=40, font_size=30, ink_color="#000000", layout="ruled"):
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
        
        # Create background based on layout
        if layout == "ruled":
            # Create ruled paper background
            image = Image.new('RGB', (int(image_width), int(image_height)), color='white')
            draw = ImageDraw.Draw(image)
            # Draw horizontal lines
            line_spacing = 30
            for y in range(padding, int(image_height), line_spacing):
                draw.line([(padding, y), (image_width - padding, y)], fill='#000000', width=1)
        elif layout == "grid":
            # Create grid paper background
            image = Image.new('RGB', (int(image_width), int(image_height)), color='white')
            draw = ImageDraw.Draw(image)
            # Draw grid lines
            grid_spacing = 20
            for x in range(padding, int(image_width), grid_spacing):
                draw.line([(x, padding), (x, image_height - padding)], fill='#000000', width=1)
            for y in range(padding, int(image_height), grid_spacing):
                draw.line([(padding, y), (image_width - padding, y)], fill='#000000', width=1)
        elif layout == "dots":
            # Create dotted paper background
            image = Image.new('RGB', (int(image_width), int(image_height)), color='white')
            draw = ImageDraw.Draw(image)
            # Draw dots
            dot_spacing = 20
            for x in range(padding, int(image_width), dot_spacing):
                for y in range(padding, int(image_height), dot_spacing):
                    draw.point((x, y), fill='#000000')
        else:
            # Create blank paper background
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
        app.logger.error(f"Error generating image: {str(e)}")
        raise

def get_available_fonts():
    fonts = []
    for font_file in os.listdir(FONTS_FOLDER):
        if font_file.endswith('.ttf'):
            font_name = os.path.splitext(font_file)[0]
            try:
                # Create a preview image for the font
                preview_path = os.path.join('font_previews', f"{font_name}.png")
                full_preview_path = os.path.join(FONT_PREVIEWS_FOLDER, f"{font_name}.png")
                
                # Generate preview if it doesn't exist
                if not os.path.exists(full_preview_path):
                    generate_font_preview(os.path.join(FONTS_FOLDER, font_file), full_preview_path)
                
                fonts.append({
                    'name': font_name,
                    'file': font_file,
                    'preview': preview_path
                })
            except Exception as e:
                app.logger.error(f"Error processing font {font_file}: {str(e)}")
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
        app.logger.error(f"Error generating preview for {font_path}: {str(e)}")

def generate_final_image(text_image_path, layout_choice, custom_bg_path=None):
    #Load chosen background
    if layout_choice == "custom" and custom_bg_path:
        bg=Image.open(custom_bg_path)
    else:
        bg=Image.open(f"layouts/{layout_choice}.jpg")

    text_img = Image.open(text_image_path)

    bg = bg.resize(text_img.size)

    final_img=Image.alpha_composite(bg.convert('RGBA'), text_img.convert('RGBA'))

    return final_img

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
        app.logger.error(f"Error combining images to PDF: {str(e)}")
        return False
    
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog1')
def blog1():
    return render_template('blog1.html')

@app.route('/blog2')
def blog2():
    return render_template('blog2.html')

@app.route('/blog3')
def blog3():
    return render_template('blog3.html')

@app.route('/blog4')
def blog4():
    return render_template('blog4.html')

@app.route('/blog5')
def blog5():
    return render_template('blog5.html')

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/disclaimer')
def disclaimer():
    return render_template("disclaimer.html")

@app.route('/privacypolicy')
def privacypolicy():
    return render_template("privacypolicy.html")

@app.route('/googledb73db056fd8e0dc.html')
def google_verification():
    return render_template('googledb73db056fd8e0dc.html')

@app.route('/robots.txt', methods=['GET'])
def robots_txt():
    robots_content = """User-agent: *
Disallow:

Sitemap: https://www.text2handwritten.com/sitemap.xml
"""
    return Response(robots_content, mimetype='text/plain')

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    pages = []
    today = datetime.now().date().isoformat()

    # ➤ Static URLs (no route parameters)
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0 and not rule.rule.startswith('/static'):
            url = url_for(rule.endpoint, _external=True)
            pages.append(f"""
    <url>
        <loc>{url}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>""")

    
    # Final XML output
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(pages)}
</urlset>"""

    return Response(sitemap_xml, mimetype='application/xml')

@app.route('/0f5f08bd642d45c39d3210ecb16a89d8.txt')
def indexnow_key():
    content = """0f5f08bd642d45c39d3210ecb16a89d8"""
    return Response(content, mimetype='text/plain')

def ping_indexnow(url, key, key_location):
    api_endpoint = "https://api.indexnow.org/indexnow"
    payload = {
        "host": "www.text2handwritten.com",
        "key": key,
        "keyLocation": key_location,
        "urlList": [url]
    }
    try:
        response = requests.post(api_endpoint, json=payload)
        return response.status_code, response.text
    except Exception as e:
        return 500, str(e)

status, response = ping_indexnow(
    url="https://www.text2handwritten.com/new-page-url",
    key="0f5f08bd642d45c39d3210ecb16a89d8",  # your key
    key_location="https://www.text2handwritten.com/0f5f08bd642d45c39d3210ecb16a89d8.txt"
)

print("IndexNow Response:", status, response)
    


@app.route('/terms')
def terms():
    return render_template("terms.html")

@app.route('/fonts')
def font_selector():
    fonts = get_available_fonts()
    return render_template('font_selector.html', fonts=fonts)

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            # Check if we have a file upload
            if 'pdf' in request.files:
                pdf_file = request.files['pdf']
                if pdf_file.filename == '':
                    return render_template('index.html', error="No file selected")
                    
                font_name = request.form.get('font')
                font_size = int(request.form.get('fontSize', 30))
                ink_color = request.form.get('inkColor', '#000000')
                layout = request.form.get('layout', 'ruled')
                
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
                            ink_color=ink_color,
                            layout=layout
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
        return render_template('index.html', error=f"An error occurred: {str(e)}")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

@app.route('/text-to-handwritten', methods=['GET', 'POST'])
def text_to_handwritten():
    if request.method == 'POST':
        try:
            # Get form data
            custom_text = request.form.get('custom_text', '')
            font_name = request.form.get('font')
            font_size = int(request.form.get('fontSize', 30))
            ink_color = request.form.get('inkColor', '#000000')
            layout = request.form.get('layout', 'ruled')
            
            if not custom_text or not font_name:
                return render_template('text_to_handwritten.html', 
                                      error="Please provide both text and select a font")
            
            # Generate a unique filename for the output
            unique_id = str(uuid.uuid4())[:8]
            image_path = os.path.join(OUTPUT_FOLDER, f"handwritten_text_{unique_id}.png")
            
            # Convert text to handwritten image
            text_to_handwritten_image(
                custom_text,
                font_name,
                image_path,
                font_size=font_size,
                ink_color=ink_color,
                layout=layout
            )
            
            # Generate PDF from the image
            pdf_path = os.path.join(OUTPUT_FOLDER, f"handwritten_text_{unique_id}.pdf")
            combine_images_to_pdf([image_path], pdf_path)
            
            # Return success page with download links
            output_files = [
                f"/download/handwritten_text_{unique_id}.png",
                f"/download/handwritten_text_{unique_id}.pdf"
            ]
            
            return render_template('success.html', files=output_files)
        
        except Exception as e:
            app.logger.error(f"Error processing text: {str(e)}")
            return render_template('text_to_handwritten.html', error=f"An error occurred: {str(e)}")
    
    # GET request
    return render_template('text_to_handwritten.html')

if __name__ == '__main__':
    # For development purposes
    app.run(host='0.0.0.0', port=5000, debug=True)