import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from tqdm import tqdm
import configparser

def get_config_downloads():
    config = configparser.ConfigParser()
    config.read('config.ini')
    folder = config.get('downloads', 'folder')
    return folder

download_folder = get_config_downloads()

def download_lessons(session, course_name, lessons, skip_optional_recordings, skip_attachments):
    print('Download will start briefly...\n')
    #os.makedirs(course_name, exist_ok=True)
    tqdm_bars = []
    lesson_name_max_length = max(len(k) for k in lessons)
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(download_lesson,
                            session,
                            course_name,
                            k,
                            lessons[k],
                            pos,
                            lesson_name_max_length,
                            skip_optional_recordings,
                            skip_attachments
            )
            for pos, k in enumerate(lessons)
        ]
        for future in as_completed(futures):
            tqdm_bars.append(future.result())
    flush_tqdm_bars(tqdm_bars)


def download_lesson(session, course_name, lesson_name, lesson_url, tqdm_position, lesson_name_max_length, skip_optional_recordings, skip_attachments):
    
    ks = get_kaltura_session(session, lesson_url)
    main_recording_url = get_main_recording_url(session, lesson_url)
    attachments_url = get_attachments_url(session, ks, lesson_url, skip_attachments)
    sources_url = get_optional_recordings_url(session, ks, lesson_url, skip_optional_recordings)

    tqdm_total_length = get_resources_total_length(attachments_url, main_recording_url, session, sources_url)

    tqdm_bar = get_tqdm(tqdm_position, tqdm_total_length, lesson_name, lesson_name_max_length)

    download_main_recording(tqdm_bar, course_name, lesson_name, main_recording_url, session)
    download_optional_recordings(tqdm_bar, course_name, lesson_name, session, sources_url)
    download_attachments(attachments_url, tqdm_bar, course_name, lesson_name, session)

    return tqdm_bar, tqdm_position


def flush_tqdm_bars(tqdm_bars):
    for bar, _ in sorted(tqdm_bars, key=lambda t: t[1]):
        bar.close()


def get_resources_total_length(attachments_url, main_recording_url, session, sources_url):
    stream = session.get(main_recording_url, stream=True)
    tqdm_total_length = int(stream.headers.get('Content-Length'))
    stream.close()
    for attachment in attachments_url:
        tqdm_total_length += int(session.head(attachment['url']).headers.get('Content-Length'))
    for url in sources_url:
        stream = session.get(url, stream=True)
        tqdm_total_length += int(stream.headers.get('Content-Length'))
        stream.close()
    return tqdm_total_length


def download_attachments(attachments_url, bar, course_name, lesson_name, session):
    for attachment in attachments_url:
        save_file(session, bar, attachment['url'], course_name, lesson_name, attachment['filename'])


def download_optional_recordings(bar, course_name, lesson_name, session, sources_url):
    for idx, source in enumerate(sources_url):
        save_file(session, bar, source, course_name, lesson_name, f'{lesson_name}-source-{idx + 1}.mp4')


def download_main_recording(bar, course_name, lesson_name, main_recording_url, session):
    save_file(session, bar, main_recording_url, course_name, lesson_name, f'{lesson_name}.mp4')


def save_file(session, bar, url, course_name, lesson_name, filename):
    folder_path = os.path.join(clean_name(download_folder), clean_name(course_name), clean_name(lesson_name))
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, clean_name(filename))
    
    with open(file_path, 'wb') as file:
        stream = session.get(url, stream=True)
        for chunk in stream.iter_content(chunk_size=1024):
            file.write(chunk)
            bar.update(len(chunk))


def get_tqdm(position, total, lesson_name, longest_desc):
    return tqdm(position=position,
                leave=True,
                desc=f"{lesson_name:<{longest_desc}}",
                dynamic_ncols=False,
                total=total,
                unit='B',
                unit_scale=True,
                bar_format="{l_bar}{bar}|{n_fmt}/{total_fmt} [{rate_fmt}]",
                unit_divisor=1024)


def get_attachments_url(session, ks, lesson_url, skip_attachments):
    if not skip_attachments:
        url = 'https://kmc.l2l.cineca.it/api_v3/index.php'
        entry_id = get_entry_id(session, lesson_url)
        params = {
            'service': 'attachment_attachmentasset',
            'apiVersion': '3.1',
            'expiry': '86400',
            'clientTag': 'kwidget:v2.98',
            'format': '1',
            'ignoreNull': '1',
            'action': 'list',
            'filter:entryIdEqual': entry_id,
            'ks': ks
        }
        response = session.get(url, params=params)
        response = json.loads(response.text)
        attachments = []
        if 'objects' in response:
            for entry in response['objects']:
                if entry['objectType'] == 'KalturaAttachmentAsset':
                    attachments.append({
                        'filename': entry['filename'],
                        'url': get_attachment_url(session, ks, entry['id'])
                    })
        return attachments
    else:
        return []


def get_attachment_url(session, ks, attachment_id):
    url = 'https://kmc.l2l.cineca.it/api_v3/index.php'
    params = {
        'service': 'attachment_attachmentasset',
        'apiVersion': '3.1',
        'expiry': '86400',
        'clientTag': 'kwidget:v2.98',
        'format': '1',
        'ignoreNull': '1',
        'action': 'geturl',
        'id': attachment_id,
        'ks': ks
    }
    response = session.get(url, params=params)
    return response.text.replace('\\', '').replace('"', '')


def get_optional_recordings_url(session, ks, lesson_url, skip_optional_recordings):
    if not skip_optional_recordings:
        entry_id = get_entry_id(session, lesson_url)
        url = 'https://kmc.l2l.cineca.it/api_v3/index.php'
        params = {
                'service': 'baseEntry',
                'apiVersion': '3.1',
                'expiry': '86400',
                'clientTag': 'kwidget:v2.98',
                'format': '1',
                'ignoreNull': '1',
                'action': 'list',
                'filter:objectType': 'KalturaBaseEntryFilter',
                'filter:typeEqual': '1',
                'filter:parentEntryIdEqual': entry_id,
                'ks': ks
            }
        response = session.get(url, params=params)
        response = json.loads(response.text)
        sources = []
        if 'objects' in response:
            for entry in response['objects']:
                url = entry['dataUrl']
                sources.append(url)
        return sources
    else:
        return []


def get_entry_id(session, lesson_url):
    response = session.get(lesson_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    iframe = soup.find('iframe')['src']
    parsed_iframe = urlparse(iframe)
    query_params = parse_qs(parsed_iframe.query)
    source = query_params['source'][0]
    parsed_source = urlparse(source)
    path = parsed_source.path
    path_parts = path.strip('/').split('/')
    return path_parts[4]


def get_main_recording_url(session, lesson_url):
    media_url_template = 'https://kmc.l2l.cineca.it/p/113/sp/11300/playManifest/entryId/{}/format/url/protocol/https/a.mp4'
    return media_url_template.format(get_entry_id(session, lesson_url))


def get_kaltura_session(session, lesson_url):
    response = session.get(lesson_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    response = session.get(soup.find('iframe')['src'])
    soup = BeautifulSoup(response.content, 'html.parser')
    url = soup.find('form')['action']
    inputs = soup.find_all('input')
    data = {input_tag.get('name'): input_tag.get('value') for input_tag in inputs if input_tag.get('name')}

    response = session.post(url=url, data=data)
    soup = BeautifulSoup(response.content, 'html.parser')
    script_tags = soup.find_all('script')
    for script_tag in script_tags:
        if script_tag.string:
            url_match = re.search(r"window\.location\.href\s*=\s*['\"](.*?)['\"]", script_tag.string)
            if url_match:
                url = url_match.group(1)
    response = session.get(url=url)
    soup = BeautifulSoup(response.content, 'html.parser')
    script_tags = soup.find_all('script')
    flashvars_pattern = re.compile(r'var flashvars = ({.*?});', re.DOTALL)
    flashvars_json = None
    for script_tag in script_tags:
        if script_tag.string:
            match = flashvars_pattern.search(script_tag.string)
            if match:
                flashvars_json = match.group(1)
                break
    return json.loads(flashvars_json)['ks']

def clean_name(name):
    name = name.replace(',', '-')  # Replace ',' with '-'
    name = name.replace(':', '-')  # Replace ':' with '-'
    name = re.sub(r'[\/\\*?"<>|]', '', name)  # Remove invalid characters
    return name

