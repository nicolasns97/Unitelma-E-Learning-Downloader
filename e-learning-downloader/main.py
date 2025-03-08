import os
import threading
import inquirer
from bs4 import BeautifulSoup
from tqdm import tqdm
from auth import login
from config import config
from constants import SKIPPABLE_COURSES
from download import download_lessons, clean_name


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


def prepend_index_to_lessons(lessons: dict) -> dict:
    return {f'{i+1}. {key}': lessons[key] for i, key in enumerate(lessons)}


def filter_lessons(lessons: dict, selected_lessons: list) -> dict:
    return {key: value for key, value in lessons.items() if key in selected_lessons}


def main():
    tqdm.set_lock(threading.Lock())

    username = config['credentials']['username']
    password = config['credentials']['password']

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
    print('Download will start shortly...\n')
    download_lessons(session, selected_course, prepend_index_to_lessons(filter_lessons(lessons, selected_lessons)))
    print(f"\nRecordings saved at {os.path.join(config['downloads']['folder'], clean_name(selected_course))}\n")


if __name__ == "__main__":
    main()