from io import BytesIO
import requests
import os
import google.generativeai as genai
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Function to scrape the content of a given URL
def scrape_website(url):
    try:
        # Send a GET request to fetch the website content
        response = requests.get(url)
        response.raise_for_status()  # Raise exception if request failed
        return response.text  # Return the HTML content
    except requests.RequestException as e:
        # Handle errors during the request
        print(f"Error occurred while fetching the website: {e}")
        return None

# Function to extract the source domain from the URL
def get_source(url):
    # Parse the URL to get the domain
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    return domain.replace('www.', '')  # Return the domain without 'www.'

# Function to summarize the scraped content using a generative AI model
def summarize_and_extract_info(html_content, source):
    # Configure the generative AI with the provided API key
    genai.configure(api_key='AIzaSyBbIXunjiwerHsfUGwzhQwor1pG00-gBt0')

    # Define generation configuration for the AI model
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    # Initialize the generative AI model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-exp-0827",  # Model name for the AI
        generation_config=generation_config,  # Set the configuration
    )

    # Start a chat session with the AI model and send the request
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    f"```\n{html_content}\n```",  # Provide HTML content to the model
                    f"Please summarize the news content above into a maximum of 200 characters and find a usable image URL from the HTML elements. The news source is {source}. Summarize briefly, concisely, and make it eye-catching or clickbait like creating a news headline\nAvoid using Emojis and use Content Language as Language example Indonesia\nFormat the response as:\n```\nSummary: {{Summary}}\nURL Image: {{Image URL from HTML Element}}\nSource: {source}\n```",
                ],
            },
        ]
    )

    # Send the message to the AI model to get the summary and image URL
    response = chat_session.send_message("Provide news summary, image URL, and source")
    return response.text

# Function to create an image with a summarized text overlay
def create_image_output(text, source, background_image_url, output_file):
    # Download the background image from the URL
    response = requests.get(background_image_url)
    background = Image.open(BytesIO(response.content))
    
    # Calculate aspect ratios for resizing the background image
    aspect_ratio_bg = background.width / background.height
    aspect_ratio_target = 1080 / 1080  # Target aspect ratio for square image

    # Resize and crop the background image to fit a 1080x1080 square
    if aspect_ratio_bg > aspect_ratio_target:
        # Background image is wider than the target
        new_height = 1080
        new_width = int(new_height * aspect_ratio_bg)
    else:
        # Background image is taller or square
        new_width = 1080
        new_height = int(new_width / aspect_ratio_bg)
    
    # Resize the background image
    background = background.resize((new_width, new_height), Image.LANCZOS)
    
    # Calculate coordinates to crop the image to 1080x1080
    left = (new_width - 1080) / 2
    top = (new_height - 1080) / 2
    right = left + 1080
    bottom = top + 1080
    
    # Crop the image
    background = background.crop((left, top, right, bottom))
    
    # Create a new blank image (white) to hold the background and text
    img = Image.new('RGB', (1080, 1080), color='white')
    img.paste(background, (0, 0))
    
    # Prepare to draw text on the image
    draw = ImageDraw.Draw(img)
    
    # Draw a white rectangle where the text will be placed
    rect_top = 600
    rect_bottom = 1040
    rect_left = 40
    rect_right = 1040
    draw.rectangle([(rect_left, rect_top), (rect_right, rect_bottom)], fill='white')
    
    available_width = rect_right - rect_left - 40  # Available width for the text
    available_height = rect_bottom - rect_top - 80  # Available height for the text

    # Helper function to get the size of the text box
    def get_text_size(text, font):
        return draw.multiline_textbbox((0, 0), text, font=font)

    font_size = 120  # Initial font size
    font = ImageFont.truetype("arial.ttf", font_size)
    
    # Adjust font size to fit within the available space
    while True:
        wrapped_text = textwrap.fill(text, width=30)
        bbox = get_text_size(wrapped_text, font)
        if bbox[2] - bbox[0] <= available_width and bbox[3] - bbox[1] <= available_height * 0.9:
            break
        font_size -= 2
        if font_size < 36:  # Minimum font size limit
            font_size = 36
            break
        font = ImageFont.truetype("arial.ttf", font_size)

    # Draw the text onto the image
    draw.text((rect_left + 20, rect_top + 20), wrapped_text, font=font, fill='black')

    # Adjust font size for the source text and draw it at the bottom-right corner
    source_font_size = max(24, int(font_size * 0.6))  # Smaller font for the source
    source_font = ImageFont.truetype("arial.ttf", source_font_size)
    source_text = f"Source: {source}"
    source_bbox = draw.textbbox((0, 0), source_text, font=source_font)
    source_width = source_bbox[2] - source_bbox[0]
    source_height = source_bbox[3] - source_bbox[1]
    draw.text((rect_right - source_width - 20, rect_bottom - source_height - 20), source_text, font=source_font, fill='black')
    
    # Save the final image to the specified output file
    img.save(output_file)

# Function to parse the AI output into structured data
def parse_output(output):
    lines = output.strip().split('\n')
    result = {}
    # Extract the summary, image URL, and source from the output
    for line in lines:
        if line.startswith('Summary:'):
            result['summary'] = line.split('Summary:', 1)[1].strip()
        elif line.startswith('URL Image:'):
            result['url_image'] = line.split('URL Image:', 1)[1].strip()
        elif line.startswith('Source:'):
            result['source'] = line.split('Source:', 1)[1].strip()
    return result

# Function to save the summarized content to a text file
def save_to_file(content, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f"Output successfully saved to {filename}")

# Main script usage
url = input("Enter News Link: ")
output_file_txt = "scraping_result.txt"
output_file_img = "scraping_result.png"

# Scrape the website content
html_content = scrape_website(url)
if html_content:
    # Get the source domain from the URL
    source = get_source(url)
    
    # Summarize and extract information using the AI model
    result = summarize_and_extract_info(html_content, source)
    save_to_file(result, output_file_txt)  # Save the result to a text file
    
    # Parse the result to get summary and image URL
    parsed_result = parse_output(result)
    text_for_image = parsed_result['summary']
    
    # Create the final image with the summary and source
    create_image_output(text_for_image, parsed_result['source'], parsed_result['url_image'], output_file_img)
    print(f"Image output successfully saved to {output_file_img}")
else:
    print("Failed to retrieve website content.")
