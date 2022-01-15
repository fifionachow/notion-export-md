from datetime import datetime
import logging
import requests
from urllib import parse, request

log_level = logging.INFO
log_format = '[%(asctime)s] [%(levelname)s] - %(message)s'
logging.basicConfig(level=log_level, format=log_format)

IMG_FORMAT_DELIM = '|**|'

def text_formatter(content_type, content, color=None):
    default_handler = lambda content: f"{content}\n"

    handlers = {
        "bold": lambda content: f"**{content}**",
        "italic": lambda content: f"*{content}*",
        "code": lambda content: f"`{content}`",
        "strikethrough": lambda content: f"~~{content}~~",
        "color": lambda content: f'<span style="color:{color}">{content}</span>'
    }

    try:
        handler = handlers.get(content_type, default_handler)(content)
    except KeyError as e:
        logging.debug(f'{content_type} not supported in markdown')
        return default_handler
    
    return handler


def apply_md_styles(content, formatting):
    logging.debug(f'Apply MD Style: {content}')
    md_content = content

    inline_html_formatting = []

    for format_type, format_val in formatting.items():
        if not format_val or format_val == 'default':
            # Skip this format type
            continue
        elif format_type == 'color' and format_val != 'default':
            inline_html_formatting.append(format_type)
        else:
            md_content = text_formatter(format_type, md_content)

    for html_formatting in inline_html_formatting:
        md_content = text_formatter(html_formatting, md_content, formatting[html_formatting])

    return md_content

def md_text(content, annotations):
    return apply_md_styles(content, annotations)

def join_md_text(block_content, type_key='text'):
    content = ""
    for text in block_content[type_key]:
        try:
            content += md_text(text['text']['content'], text['annotations'])
        except Exception as e:
            logging.error(f"{e} - {text.keys()} - {text}")
    return content

def md_num_list(md_content, enum):
    return f"{enum}. {md_content}"

def md_bullet_list(md_content):
    return f"- {md_content}"

def md_script(md_content):
    url = md_content['url']
    return f'<script src="{url}"></script>'

def md_html(html):
    hugo_html_shortcode = "{{{{{html_code}}}}}"
    return hugo_html_shortcode.format(html_code=html)

def md_quote(block_content):
    quote = '>{text}'
    content = "\n".join([quote.format(text=md_text(text['text']['content'], text['annotations'])) for text in block_content['text']])
    return content

def md_caption(md_content):
    content = md_content['text']
    content_text = content['content'].split(IMG_FORMAT_DELIM)[-1]

    if md_content['href']:
        html_val = {"link_text": content_text, "link_src": content['link']['url']}
    else:
        html_val = {"text": content_text}
    
    html_str = " ".join([f'{el_key}="{el_val}"' for el_key, el_val in html_val.items()])

    html = f'<text style="font-size:9px" {html_str}>'
    return md_html(html)

def md_image(md_content, asset_dir):
    md_blocks = []
    img_format = None
    img_format_str = ''

    captions = []
    if md_content['caption']:
        img_format = get_image_format(md_content['caption'][0])
        for text in md_content['caption']:
            captions.append(md_caption(text))

    url = md_content['file']['url']
    asset_name = parse.urlparse(url).path.split('/')[-1]

    if md_content['type'] == 'file':
        # need to download and find a local home
        figure_src = f"/{asset_dir.parts[-1]}/{asset_name}"
        request.urlretrieve(url, asset_dir/asset_name)
        logging.info('Image file downloaded')
    else:
        # can stay as url
        figure_src = url

    if img_format:
        img_format_str = ' '.join([f'{f_key}="{f_val.strip()}"' for f_key, f_val in img_format.items()])
    
    html = f'<figure src={figure_src} {img_format_str}>'
    img_html = md_html(html)

    md_blocks += [img_html] + captions

    return md_blocks

def get_image_format(caption):
    def get_keyval_from_str(keyval):
        key, val = keyval.split("=")
        return {key: val}

    img_format = {}
    splitted = caption['text']['content'].split(IMG_FORMAT_DELIM)

    if len(splitted) == 2:
        for pair in splitted[0].split(';'):
            img_format = {**img_format, **get_keyval_from_str(pair)}
        return img_format

def md_heading(md_content, heading_level):
    heading = '#'
    level_num = int(heading_level.split("_")[-1])
    return f'{heading*level_num} {md_content}'