import os
import requests
import re

def download_google_fonts():
    # List of handwriting-style fonts from Google Fonts
    fonts = [
        'Dancing Script',
        'Caveat',
        'Satisfy',
        'Pacifico',
        'Indie Flower',
        'Architects Daughter',
        'Shadows Into Light',
        'Kalam',
        'Gloria Hallelujah',
        'Homemade Apple'
    ]
    
    # Create fonts directory if it doesn't exist
    fonts_dir = os.path.join('static', 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)
    
    for font in fonts:
        try:
            # Convert font name to URL format
            font_url_name = font.replace(' ', '+')
            
            # Get the CSS file from Google Fonts
            css_url = f"https://fonts.googleapis.com/css2?family={font_url_name}&display=swap"
            print(f"Fetching CSS for {font}...")
            response = requests.get(css_url)
            
            if response.status_code == 200:
                # Extract the font file URL from the CSS using regex
                font_url_match = re.search(r'src: url\((.*?)\)', response.text)
                if font_url_match:
                    font_file_url = font_url_match.group(1)
                    
                    # Download the font file
                    print(f"Downloading {font}...")
                    font_file = requests.get(font_file_url)
                    
                    if font_file.status_code == 200:
                        # Save the font file
                        font_path = os.path.join(fonts_dir, f"{font}.ttf")
                        with open(font_path, 'wb') as f:
                            f.write(font_file.content)
                        print(f"Successfully downloaded {font}")
                    else:
                        print(f"Failed to download font file for {font}")
                else:
                    print(f"Could not find font URL in CSS for {font}")
            else:
                print(f"Failed to fetch CSS for {font}")
                
        except Exception as e:
            print(f"Error processing {font}: {str(e)}")
        
        print("-" * 50)  # Separator between fonts

if __name__ == "__main__":
    print("Starting font download process...")
    download_google_fonts()
    print("Font download process completed!") 