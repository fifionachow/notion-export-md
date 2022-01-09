import os
from pathlib import Path
import json
from urllib import parse, request
import logging
from notion_client import Client

import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from data_classes.markdown import *

from config import HUGO_BACKEND_DIR, NOTION_PAGE, NOTION_DATABASE

NEW_LINE = '\n'

FM_KEYS = {
    "Draft": "draft",
    "Date": "date",
    "Name": "title",
    "Slug": "slug",
    "Tags": 'tags',
    "Series": "series"
}

def get_id_from_url(url):
    return parse.urlparse(url).path.split('/')[-1]

def get_property(property):
    _type = property['type']
    if _type in ['title', 'rich_text']:
        md_text = join_md_text(property, _type)
        return f'"{md_text}"'
    elif _type == 'select':
        md_select = property[_type]['name']
        return f'"{md_select}"'
    elif _type == 'date':
        return property[_type]['start']
    elif _type == 'multi_select':
        return json.dumps([select['name'] for select in property[_type]])
    else:
        return str(property[_type]).lower()

def create_front_matter(page: dict, front_matter_cols: dict):
    properties = page['properties']
    front_matter = {fm_col: get_property(properties[prop_col]) for prop_col, fm_col in front_matter_cols.items()}
    return front_matter

def stringify_front_matter(front_matter: dict):
    front_matter = [f"{fm_col} = {fm_val}" for fm_col, fm_val in front_matter.items()]    
    return f"+++{NEW_LINE}{NEW_LINE.join(front_matter)}{NEW_LINE}+++{NEW_LINE}"

def parse_notion_block(block_type, block_content, content, enum):
    if block_type == 'paragraph':
        content += join_md_text(block_content)
    elif block_type == 'bulleted_list_item':
        content += md_bullet_list(join_md_text(block_content))
    elif block_type == 'numbered_list_item':
        content += md_num_list(join_md_text(block_content), enum)
    elif block_type == 'embed':
        content += md_script(block_content)
    elif block_type == 'divider':
        divider = '---'
        content += divider
    elif block_type == "heading_2":
        content = md_heading(join_md_text(block_content), block_type)
    elif block_type == 'code':
        print('Not implemented yet')
    else:
        raise Exception(f'BLOCK TYPE - {block_type} - not implemented yet - {block_content}')
    return content

def get_notion_blocks(notion_client, page_id, asset_dir, content_start=""):
    returned_block = notion_client.blocks.children.list(page_id)

    md_blocks = []
    enum = 1
    
    for block in returned_block['results']:
        content = content_start
        block_type = block['type']
        block_content = block[block_type]

        if block_type == 'image':
            content = md_image(block_content, asset_dir)
        else:
            content = parse_notion_block(block_type, block_content, content)
    
        if block_type in ('numbered_list_item'):
            enum += 1
        else:
            enum = 1

        if isinstance(content, str):
            md_blocks.append(content)
        elif isinstance(content, list):
            md_blocks += content
        else:
            print(f'CONTENT TYPE UNKNOWN - {type(content)} - {content}')

        # Get children blocks
        if block['has_children']:
            content = '\t' + content
            md_blocks += get_notion_blocks(notion_client, block['id'], asset_dir, content)

    return md_blocks

if __name__ == '__main__':
    hugo_root = Path(HUGO_BACKEND_DIR)
    page_url = NOTION_PAGE
    hugo_content_root = hugo_root/'content/posts'
    static_root = hugo_root/'static'

    notion = Client(auth=os.environ["NOTION_API_KEY"], log_level=logging.INFO)

    # TODO: To get pages from Status="publishing"
    # for now, script exports 1 specific Notion page
    
    # Page Info
    page_id = get_id_from_url(page_url)
    returned_page = notion.pages.retrieve(page_id)

    # Hugo Front Matter
    front_matter = create_front_matter(returned_page, FM_KEYS)
    front_matter_str = stringify_front_matter(front_matter)
    post_slug = front_matter['slug'].replace('"','')

    # Block Info
    post_asset_dir = static_root/post_slug
    post_asset_dir.mkdir(exist_ok=True)
    notion_blocks = get_notion_blocks(notion, page_id, post_asset_dir)

    # EXPORT
    series_name = front_matter['series']
    post_name = f"{post_slug}-{page_id}.md"

    if series_name:
        out_md_file = hugo_content_root/series_name[0]/post_name
    else:
        out_md_file = hugo_content_root/post_name

    with open(out_md_file, 'w') as out_file:
        out_file.write(front_matter_str)
        out_file.write(NEW_LINE)
        out_file.write(f"{NEW_LINE*2}".join(notion_blocks))

    logging.info(f'Page extracted - {post_name}')