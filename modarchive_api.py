import requests
from xml.etree import ElementTree as ET  # Add this line to import ElementTree
from html import escape
from PIL import Image, ImageDraw, ImageFont

def get_module_by_id(api_key, module_id, include_comments=False, include_reviews=False):
    base_url = "https://modarchive.org/data/xml-tools.php"


    # Constructing the request URL
    params = {
        'key': api_key,
        'request': 'view_by_moduleid',
        'query': module_id,
        'opt-com': 1 if include_comments else 0,
        'opt-rev': 1 if include_reviews else 0,
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises HTTPError for bad responses
        return response.text

    except requests.RequestException as e:
        print(f"Error making the request: {str(e)}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

def parse_module_info(xml_text):
    module_info = {}

    try:
        # Parse XML response
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Attempt to find the module element
    module = root.find('.//module')
    if module is None:
        print("Error: Module element not found in XML.")
        return None

    # Extract module-specific information and apply HTML escaping
    module_info['filename'] = escape(module.find('filename').text)
    module_info['format'] = escape(module.find('format').text)
    module_info['url'] = escape(module.find('url').text)
    module_info['date'] = escape(module.find('date').text)
    module_info['id'] = int(module.find('id').text)
    module_info['hash'] = escape(module.find('hash').text)
    module_info['size'] = escape(module.find('size').text)
    module_info['hits'] = int(module.find('hits').text)
    module_info['songtitle'] = module.find('songtitle').text  # No escape for songtitle

    return module_info

def get_random_module_id(api_key, format=None, genre=None, channels=None, size=None):
    base_url = "https://modarchive.org/data/xml-tools.php"
    params = {'key': api_key, 'request': 'random', 'format': format, 'genreid': genre, 'channels': channels, 'size': size}

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        root = ET.fromstring(response.text)
        module_id_element = root.find('.//id')

        if module_id_element is not None:
            return module_id_element.text

    return None


# Function to search for modules
def search_modules(api_key, search_type, query, format=None, page=None, size=None, channels=None):
    base_url = "https://modarchive.org/data/xml-tools.php"

    # Constructing the request URL
    params = {
        'key': api_key,
        'request': 'search',
        'type': search_type,
        'query': query,
    }

    # Additional options
    if format:
        params['format'] = format
    if page:
        params['page'] = page
    if size:
        params['size'] = size
    if channels:
        params['channels'] = channels

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        return response.content
    else:
        print(f"Error retrieving search results: {response.status_code}")
        return None

# Function to parse search results from XML
def parse_search_results(xml_content):
    search_results = []

    try:
        root = ET.fromstring(xml_content)
        modules = root.findall('.//module')

        for module in modules:
            module_info = {
                'filename': module.find('filename').text,
                'format': module.find('format').text,
                'url': module.find('url').text,
                'date': module.find('date').text,
                'id': int(module.find('id').text),
                'hash': module.find('hash').text,
                'size': module.find('size').text,
                'hits': int(module.find('hits').text),
                'songtitle': module.find('songtitle').text,
            }
            search_results.append(module_info)

        return search_results

    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

# Function to format search results for display
def format_search_results(search_results):
    formatted_results = []

    for result in search_results:
        formatted_result = f"**ID:** {result['id']}\n" \
                           f"**Filename:** {result['filename']}\n" \
                           f"**Song Title:** {result['songtitle']}\n" \
                           f"**Format:** {result['format']}\n" \
                           f"**Date:** {result['date']}\n" \
                           f"**Size:** {result['size']} bytes\n" \
                           f"**Hits:** {result['hits']}\n"
        formatted_results.append(formatted_result)

    return formatted_results




def generate_module_info_image_with_custom_background(api_key, module_id, custom_background_path, positions):
    # Retrieve module information using the ModArchive API
    mod_info_xml = get_module_by_id(api_key, module_id, include_comments=True, include_reviews=True)

    if mod_info_xml is None:
        print("Error retrieving module information.")
        return None, None

    mod_info = parse_module_info(mod_info_xml)

    # Load the custom background image
    background_image = Image.open(custom_background_path)

    # Create a drawing object
    draw = ImageDraw.Draw(background_image)

    # Set the font
    font_path = "font.ttf"
    font_size = 20
    font = ImageFont.truetype(font_path, font_size)

    # Draw the module information on the image
    for key, position in positions.items():
        value = str(mod_info.get(key, ""))
        draw.text(position, value, fill="white", font=font)

    # Save the generated image
    output_path = f"module_info_{module_id}.png"
    background_image.save(output_path)
    print(f"Image saved at: {output_path}")
    return background_image, output_path, mod_info



def get_genre_list(api_key):
    base_url = "https://modarchive.org/data/xml-tools.php"
    
    # Constructing the request URL for genre list
    params = {
        'key': api_key,
        'request': 'view_genres',
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises HTTPError for bad responses
        return response.content

    except requests.RequestException as e:
        print(f"Error making the request: {str(e)}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

def parse_genre_xml(xml_content):
    genres = []

    try:
        # Parse XML content
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Iterate over each 'parent' element
    for parent_elem in root.findall('.//parent'):
        genre_info = {
            'name': escape(parent_elem.find('text').text),
            'id': int(parent_elem.find('id').text),
            'files': int(parent_elem.find('files').text)
        }

        # If there are children, parse them as well
        children_elem = parent_elem.find('children')
        if children_elem is not None:
            genre_info['children'] = parse_children(children_elem)

        genres.append(genre_info)

    return genres

def parse_children(children_elem):
    children = []

    # Iterate over each 'child' element
    for child_elem in children_elem.findall('.//child'):
        child_info = {
            'name': escape(child_elem.find('text').text),
            'id': int(child_elem.find('id').text),
            'files': int(child_elem.find('files').text)
        }
        children.append(child_info)

    return children

