// Common functionality for both pages
document.addEventListener("DOMContentLoaded", function() {
    // Font preview functionality
    const fontSelect = document.getElementById('fontSelect');
    const previewText = document.getElementById('previewText');
    const fontSize = document.getElementById('fontSize');
    const fontSizeValue = document.getElementById('fontSizeValue');
    const inkColor = document.getElementById('inkColor');
    const customText = document.getElementById('custom_text');

    if (fontSelect && previewText) {
        function updatePreview() {
            const selectedFont = fontSelect.value;
            if (selectedFont) {
                previewText.style.fontFamily = selectedFont;
                previewText.style.fontSize = `${fontSize.value}px`;
                previewText.style.color = inkColor.value;
                
                // Update preview text with first 50 characters from user input if available
                if (customText) {
                    const userText = customText.value;
                    if (userText.length > 0) {
                        const previewTextContent = userText.length > 50 
                            ? userText.substring(0, 50) + '...' 
                            : userText;
                        previewText.textContent = previewTextContent;
                    } else {
                        previewText.textContent = "The quick brown fox jumps over the lazy dog";
                    }
                }
            }
        }

        fontSelect.addEventListener('change', updatePreview);
        fontSize.addEventListener('input', () => {
            fontSizeValue.textContent = `${fontSize.value}px`;
            updatePreview();
        });
        inkColor.addEventListener('input', updatePreview);
        if (customText) {
            customText.addEventListener('input', updatePreview);
        }
    }

    // Layout selector functionality
    const layoutSelector = document.getElementById('layoutSelector');
    const layoutPreview = document.getElementById('layoutPreview');
    const customBackground = document.getElementById('customBackgroud');

    if (layoutSelector && layoutPreview) {
        layoutSelector.addEventListener('change', function() {
            const selectedLayout = this.value;
            layoutPreview.className = 'layout-preview ' + selectedLayout;
            
            if (selectedLayout === 'custom') {
                customBackground.style.display = 'block';
            } else {
                customBackground.style.display = 'none';
            }
        });

        if (customBackground) {
            customBackground.addEventListener('change', function(e) {
                if (e.target.files && e.target.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        layoutPreview.style.backgroundImage = `url(${e.target.result})`;
                        layoutPreview.style.backgroundSize = 'cover';
                    }
                    reader.readAsDataURL(e.target.files[0]);
                }
            });
        }
    }

    // Mode toggle functionality (for index page)
    const pdfBtn = document.getElementById('pdfBtn');
    const textBtn = document.getElementById('textBtn');
    const pdfSection = document.getElementById('pdfSection');
    const textSection = document.getElementById('textSection');

    if (pdfBtn && textBtn) {
        pdfBtn.addEventListener('click', function(e) {
            e.preventDefault();
            pdfBtn.classList.add('active');
            textBtn.classList.remove('active');
            pdfSection.classList.add('active');
            textSection.classList.remove('active');
        });

        textBtn.addEventListener('click', function(e) {
            e.preventDefault();
            textBtn.classList.add('active');
            pdfBtn.classList.remove('active');
            textSection.classList.add('active');
            pdfSection.classList.remove('active');
        });
    }

    // Form submission loading state
    const convertForm = document.getElementById('convertForm');
    const textForm = document.getElementById('textForm');
    
    if (convertForm) {
        convertForm.addEventListener('submit', function() {
            document.querySelector('.loading').classList.remove('d-none');
        });
    }
    
    if (textForm) {
        textForm.addEventListener('submit', function() {
            document.querySelector('.loading').classList.remove('d-none');
        });
    }

    // Mobile menu toggle
    const toggle = document.getElementById('menu-toggle');
    const navLinks = document.getElementById('nav-links');

    if (toggle && navLinks) {
        toggle.addEventListener('click', () => {
            navLinks.classList.toggle('show');
        });
    }
});