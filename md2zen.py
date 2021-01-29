#!/usr/bin/env python3

from zendeskhc.HelpCenter import HelpCenter
from bs4 import BeautifulSoup as bs4
import json
import os
import subprocess
import configparser
from glob import glob
import logging
from datetime import datetime

ROOT_SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))  # top source directory
LOG_FILE_DIR = os.path.join(ROOT_SOURCE_DIR,'logs')
LOGGING_FORMAT = '%(name)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)
ERROR_CODE = 1
OK_CODE = 0

CONFIG_FILE = 'zenhub-token'
EXCLUDED_HTML_FILENAMES = ['index', 'genindex', 'search'] # these files will not be carried over to Zendesk

# ids for zendesk are hardcoded for now. Need to be made configurable via some API calls.
ARTICLE_DICT =  {
    "article": {
        "body": "",
        "locale": "en-us",
        "permission_group_id": 1326317,
        "title": "",
        "user_segment_id": 360000471977
    },
    "notify_subscribers": False
}
SECTION_ID = 360003315137


def read_config_file(configfilepath=CONFIG_FILE): # will return a dict
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    cfg = config['DEFAULT'] # KISS for now.
    config_dict = {key:cfg[key] for key in cfg.keys()}
    return config_dict

def gen_jupyter_book(source_folder_path, cwd=None):
    cmd_string = f"jupyter-book build {source_folder_path}"
    result = subprocess.run(cmd_string, shell=True, cwd=cwd)
    st_code = result.returncode
    logger.info(f'jupyter-book build STATUS CODE = {st_code}')
    return st_code

def gen_list_of_html_files(source_folder_path):
    # first we find all the html files in the path
    html_folder_path = os.path.join(source_folder_path, "_build", "html")
    html_folder_glob_path = os.path.join(html_folder_path,"*.html")
    html_file_paths_list = glob(html_folder_glob_path)
    excluded_html_file_paths_list = [os.path.join(html_folder_path, x + ".html") for x in EXCLUDED_HTML_FILENAMES]
    # now we exclude the files that jupyter adds to make an independent book
    final_html_file_paths_list = list(set(html_file_paths_list) - set(excluded_html_file_paths_list))
    logger.info(f'Final List of html files to be sent to Zendesk: \n {final_html_file_paths_list}')
    return final_html_file_paths_list

def update_article_dict(html_file_path, article_dict=ARTICLE_DICT):
    with open(html_file_path,'r') as f:
        soup = bs4(f.read(),'html.parser')
    article_dict['article']['title'] = soup.title.text
    article_dict['article']['body'] = soup.find(id="main-content").prettify()
    return article_dict
    
def find_section_id_from_zendesk(hc, section_name):
    sections_list = hc.list_all_sections()
    for item in sections_list:
        if item['name'] == section_name:
            return item['id']
    # item not found
    return None


def main(source_folder_path, section_name=None):
    # 0. Initialize Zendesk router
    # 1. Generate the html from the markdown files.
    # 2. Create a list of html files that need to be exported to zendesk
    # 3. For each file:
    #    a. extract only the relevant body portion that will be exported.
    #    b. prepare payload () {}
    #    c. Check if the file already exists on zendesk hc.
    #        - If yes then use PUT
    #        - If no then use POST

     # 0. Initialize Zendesk router
    zdc = read_config_file()
    hc = HelpCenter(zdc['url'], zdc['username'], zdc['token'])
    st_code = gen_jupyter_book(source_folder_path)
    if st_code != OK_CODE:
        print('Error in creating Jupyter Book.')
        exit(1)
    # 1. Generate the html from the markdown files.
    html_file_paths = gen_list_of_html_files(source_folder_path)
    # Find section id
    section_id = None #find_section_id_from_zendesk(hc, section_name)
    if section_id is None:
        section_id = SECTION_ID
    for f in html_file_paths:
        logger.info(f'Processing: {f}')
        article_dict = update_article_dict(f)
        response_json = hc.create_article(section_id, json.dumps(article_dict))
        logger.info(f"Article ID: {response_json['article']['id']}, Article URL: {response_json['article']['html_url']}")



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="This utility creates jupyterbook html from .md files and uploads them to zendesk",
        epilog=''' 
            Examples of the command are: 
            ./md2zen.py <path/to/bookdirectory> [--sectionname "section name"]
            ''', formatter_class=argparse.RawTextHelpFormatter) 
    parser.add_argument("bookdir",
                        help='''
        A directory path where the source markdown files for the book reside
        A sample book is found at ./example/mynewbook/
        ''')
    parser.add_argument("-sn", "--sectionname", help='Name of the Section to put the files in')
    args = parser.parse_args()
    print(args)
    book_dir_path = os.path.abspath(args.bookdir)
    # set up logging
    book_dir_name = os.path.basename(book_dir_path)
    current_utc_datetime = datetime.utcnow()
    dt_stamp = current_utc_datetime.strftime("%m-%d-%Y:%H:%M:%SZ")
    log_file_name = f'{book_dir_name}_{dt_stamp}.log'
    log_file_path = os.path.join(LOG_FILE_DIR,log_file_name)
    os.makedirs(LOG_FILE_DIR, exist_ok=True)
    logging.basicConfig(
        filename=log_file_path,
        level=logging.DEBUG,
        filemode='w',
        format=LOGGING_FORMAT
    )
    main(book_dir_path)
