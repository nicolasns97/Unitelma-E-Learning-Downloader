import os
import threading
from bs4 import BeautifulSoup
from tqdm import tqdm
from auth import login, get_config_credentials
import inquirer
import argparse


from constants import SKIPPABLE_COURSES
from download import download_lessons


def get_courses(session):
    response = session.get(url='https://elearning.unitelma.it')
    soup = BeautifulSoup(response.text, 'html.parser')
    columnleft_div = soup.find('div', class_='columnleft').find('section').find('section')
    links = columnleft_div.find_all('a', title=True, href=True)
    courses = {}
    for link in links:
        title = link.get('title').strip()
        href = link.get('href')
        if title not in SKIPPABLE_COURSES:
            courses[title] = href
    return courses

def get_lessons(session, course_url):
    response = session.get(course_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a',
                          href=lambda href: href and href.startswith('https://elearning.unitelma.it/mod/kalvidres/'))
    lessons = {}
    for link in links:
        url = link['href']
        span = link.find('span')
        span_text = ''.join([str(el) for el in span.contents if isinstance(el, str)]).strip()
        lessons[span_text] = url
    return lessons


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-optional-recordings', action='store_true', help='ignores optional recordings')
    parser.add_argument('--skip-attachments', action='store_true', help='ignores attachments')
    args = parser.parse_args()
    return args.skip_optional_recordings, args.skip_attachments


def main():
    skip_optional_recordings, skip_attachments = get_arguments()

    tqdm.set_lock(threading.Lock())

    password, username = get_config_credentials()

    print("Logging in...\n")
    session = login(username, password)

    print("Retrieving courses...\n")
    courses = get_courses(session)
    prompt_courses = [
        inquirer.List(
            'choice',
            message='Select a course',
            choices=courses.keys()
        )
    ]
    selected_course = inquirer.prompt(prompt_courses)['choice']
    print(f"Retrieving lessons from {selected_course}...\n")
    lessons = get_lessons(session, courses[selected_course])
    prompt_lessons = [
        inquirer.Checkbox(
            'choices',
            message='Select one or more recordings',
            choices=lessons.keys()
        )
    ]
    selected_lessons = inquirer.prompt(prompt_lessons)['choices']
    download_lessons(session, selected_course, {k: v for k, v in lessons.items() if k in selected_lessons}, skip_optional_recordings, skip_attachments)
    print(f"\nRecordings saved at {os.path.join(os.getcwd(), selected_course)}\n")


if __name__ == "__main__":
    main()