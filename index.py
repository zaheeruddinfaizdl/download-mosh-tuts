import os
import sys
import json
import signal
import requests

from pathlib import Path
from typing import Dict, List

from tqdm import tqdm
from bs4.element import Tag
from bs4 import BeautifulSoup

args_file = open('args.json', 'r')
args = json.load(args_file)
base_url = args['base_url']
request_headers = args['request_headers']
current_section_index = 0
current_chapter_index = 0

context = {}


def download_markup(url: str):
    res = requests.get(url=url, headers=request_headers)
    if res.status_code == 200:
        return res.text
    raise Exception('Server response failed')


def clean_bs4_list(bs4_list: List[BeautifulSoup]) -> List[BeautifulSoup]:

    cleaned_bs4_list: List[BeautifulSoup] = []
    for bs4_obj in bs4_list:
        if isinstance(bs4_obj, (Tag)):
            cleaned_bs4_list.append(bs4_obj)

    return cleaned_bs4_list


def append_mp4_ext(file_name: str):
    return file_name + '.mp4'


def get_cleaned_file_name(un_cleaned_file_name: str):
    cleaned_name = " ".join(un_cleaned_file_name.split(' '))
    cleaned_name = "".join(cleaned_name.split('    '))
    cleaned_name = cleaned_name.replace("\r", "").replace("\n", "")
    return cleaned_name


def get_chapter_download_link(chapter_markup_str: str) -> str:
    soup = BeautifulSoup(chapter_markup_str, 'html.parser')
    chapter_download_link = soup.find('a', 'download', href=True)

    if chapter_download_link != None:
        return chapter_download_link['href']

    return ""


def download_chapter_video(download_dir: str, url: str, video_name:str):
    with requests.get(url, headers=request_headers, stream=True) as r:
        r.raise_for_status()
        download_path = download_dir + '/' + video_name
        print(f'Downloading {download_path}')
        with open(download_path, 'wb') as f:
            for chunk in tqdm(r.iter_content(chunk_size=8192)):
                f.write(chunk)

    return 'OK'


def process_section_chapters(section_dir: str, section_chapters: List[BeautifulSoup]):

    global current_chapter_index

    for section_chapter in section_chapters[current_chapter_index:]:
        chapter_name = section_chapter.get_text(strip=True)
        cleaned_chapter_file_name = get_cleaned_file_name(chapter_name)
        file_name_with_ext = append_mp4_ext(cleaned_chapter_file_name)
        rel_chapter_url = section_chapter.find('a', href=True)['href']
        abs_chapter_url = base_url + rel_chapter_url
        chapter_markup = download_markup(url=abs_chapter_url)
        chapter_download_link = get_chapter_download_link(chapter_markup)
        abs_chapter_download_link = base_url + chapter_download_link
        if abs_chapter_download_link:
            download_path = section_dir  # + "/" + file_name_with_ext
            download_chapter_video(download_dir=download_path,
                                   url=abs_chapter_download_link, video_name=file_name_with_ext)
        else:
            print(f'Skipping chapter {chapter_name}')

        # increment chapter index at end of each iteration

        current_chapter_index += 1


def mk_section_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def cache_markup(markup, path):
    file = open(path, 'w')
    file.write(markup)
    file.close()


def get_cached_markup(path):
    file = open(path, 'r')
    markup = file.read()
    file.close()
    return markup


def load_context():
    f = open('context.json', 'r')

    return json.load(f)


def dump_context(context: Dict):
    print('Dumping context', json.dumps(context))
    f = open('context.json', 'w')
    json.dump(context, f)
    f.close()


def signal_handler(sig, frame):
    context["current_section_index"] = current_section_index
    context["current_chapter_index"] = current_chapter_index
    dump_context(context)
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":

    markup_file_name = args['course_base_link'].split('/')[-1] + '.html'
    base_html = ''

    context = load_context()

    if os.path.isfile(markup_file_name):
        base_html = get_cached_markup(markup_file_name)
    else:
        base_html = download_markup(url=args['course_base_link'])
        cache_markup(base_html, markup_file_name)

    soup = BeautifulSoup(base_html, 'html.parser')
    course_sections = soup.find_all("div", 'col-sm-12 course-section')

    current_section_index = context["current_section_index"]
    current_chapter_index = context["current_chapter_index"]

    for course_section in course_sections[current_section_index:]:
        course_section_content = course_section.contents
        cleaned_course_section_content = clean_bs4_list(course_section_content)
        # at [0] -> Course section title
        section_title = cleaned_course_section_content[0]
        # at [1] -> Course section chapters list
        sections_chapters = cleaned_course_section_content[1]

        section_path = os.path.join(
            args['output_dir_path'], section_title.get_text(strip=True))
        mk_section_dir(section_path)
        cleaned_sections_chapters = clean_bs4_list(sections_chapters)
        process_section_chapters(section_path, cleaned_sections_chapters)
        # Increment section index at the end of each iteration
        current_section_index += 1
        # reset the chapter index to 0 at the end of each iternation
        current_chapter_index = 0
