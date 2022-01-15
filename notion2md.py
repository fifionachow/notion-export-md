import os
import sys
from pathlib import Path
import json
from urllib import parse, request
import logging
import subprocess
import argparse

from markdown import *
from config import HUGO_BACKEND_DIR, NOTION_PAGE, NOTION_DATABASE, GH_USER, GH_REPO
from gh_utils import create_pull_request

from notion_client import Client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

log_level = logging.INFO
log_format = '[%(asctime)s] [%(levelname)s] - %(message)s'
logging.basicConfig(level=log_level, format=log_format)

READY_STATUS = 'Ready to Publish'
NEW_LINE = '\n'
FM_KEYS = {
    "Draft": "draft",
    "Date": "date",
    "Name": "title",
    "Slug": "slug",
    "Tags": 'tags',
    "Series": "series"
}

slugs = []

def get_id_from_url(url):
    url_path = parse.urlparse(url).path
    url_page = url_path.split('/')[-1]
    return url_page.split('-')[-1]

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
    elif block_type.startswith("heading"):
        content = md_heading(join_md_text(block_content), block_type)
    elif block_type == 'code':
        logging.error('Not implemented yet')
    elif block_type == 'quote':
        content = md_quote(block_content)
    else:
        raise Exception(f'BLOCK TYPE - {block_type} - not implemented yet - {block_content}')
    return content

def get_notion_blocks(notion_client, page_id, asset_dir, content_start="", is_child=False):
    returned_block = notion_client.blocks.children.list(page_id)

    md_blocks = []
    enum = 1
    
    for block in returned_block['results']:
        block_type = block['type']
        block_content = block[block_type]

        if is_child:
            content = '\t' + content_start
        else:
            content = content_start

        if block_type == 'image':
            content = md_image(block_content, asset_dir)
        else:
            content = parse_notion_block(block_type, block_content, content, enum)
    
        if block_type in ('numbered_list_item'):
            enum += 1
        else:
            enum = 1

        if isinstance(content, str):
            md_blocks.append(content)
        elif isinstance(content, list):
            md_blocks += content
        else:
            logging.error(f'CONTENT TYPE UNKNOWN - {type(content)} - {content}')

        # Get children blocks
        if block['has_children']:
            content = content_start
            md_blocks += get_notion_blocks(notion_client, block['id'], asset_dir, content_start=content, is_child=True)

    return md_blocks

def notion2md(notion, page_id, static_root, hugo_content_root):
    returned_page = notion.pages.retrieve(page_id)

    # Hugo Front Matter
    front_matter = create_front_matter(returned_page, FM_KEYS)
    front_matter_str = stringify_front_matter(front_matter)
    post_slug = front_matter['slug'].replace('"','')
    slugs.append(post_slug)

    # Block Info
    post_asset_dir = static_root/post_slug
    post_asset_dir.mkdir(exist_ok=True)
    notion_blocks = get_notion_blocks(notion, page_id, post_asset_dir)

    # EXPORT
    series_name = json.loads(front_matter['series'])
    post_name = f"{post_slug}-{page_id.replace('-', '')}.md"

    if series_name:
        out_md_dir = hugo_content_root/series_name[0]
        out_md_dir.mkdir(exist_ok=True, parents=True)
        out_md_file = out_md_dir/post_name
    else:
        out_md_file = hugo_content_root/post_name

    with open(out_md_file, 'w') as out_file:
        out_file.write(front_matter_str)
        out_file.write(NEW_LINE)
        out_file.write(f"{NEW_LINE*2}".join(notion_blocks))

    logging.info(f'Page extracted - {post_name}')
    return post_slug

def publish_to_gitpages(slug):
    custom_message = f"Added/updated post - {slug}"
    deployment_script = f"{SCRIPT_DIR}/deploy.sh"
    subprocess.call(['sh', deployment_script, custom_message])

def update_notion_page_status(notion, page_id):
    page_status = "Published"
    update_payload = {"properties":{"Status":{"select":{"name":page_status}}}}
    
    returned_request = notion.pages.update(page_id, **update_payload)
    updated_status = returned_request['properties']['Status']['select']['name']
    logging.debug(f'Updated: {returned_request}')

    if updated_status == page_status:
        logging.info('Notion Page status updated')

def get_notion_posts(notion, database_id, status):
    query = {
            "database_id": database_id,
            "filter":{"property":"Status","select":{"equals":status}}
        }

    results = notion.databases.query(**query)['results']
    page_ids = [result['id'] for result in results]
    return page_ids

def main(publish=False):
    hugo_root = Path(HUGO_BACKEND_DIR)
    hugo_content_root = hugo_root/'content/posts'
    static_root = hugo_root/'static'
    
    notion = Client(auth=os.environ["NOTION_API_KEY"], log_level=logging.ERROR)

    if NOTION_PAGE:
        page_id = get_id_from_url(NOTION_PAGE)
        ready_list = [page_id]
    else:
        database_id = get_id_from_url(NOTION_DATABASE)
        ready_list = get_notion_posts(notion, database_id, status=READY_STATUS)

    logging.info(f"Notion posts ready for publishing - {len(ready_list)}")

    for page_id in ready_list:
        post_slug = notion2md(notion, page_id, static_root, hugo_content_root)
        if publish:
            publish_to_gitpages(post_slug)
            update_notion_page_status(notion, page_id)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action='store_false')
    args = parser.parse_args()

    # exports Notion page(s) as markdowns
    main(publish=args.publish)

    pr_title = f"Articles to publish - {len(slugs)}"
    pr_body = f'List of new/updated articles:\n{"\n".join(slugs)}'
    pr_link = create_pull_request(GH_USER, GH_REPO, title=pr_title, body=pr_body)
    logging.info(f"Pull Request created - {pr_link}")