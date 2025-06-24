import os
import threading
import inquirer
from bs4 import BeautifulSoup
from tqdm import tqdm
from auth import login
from config import config
from constants import SKIPPABLE_COURSES, RETURN_TO_MAIN_MENU, DOWNLOAD_ALL_LESSONS
from download import download_lessons, clean_name


class Prompt_outputs:
    def __init__(self, selected_course, lessons, selected_lessons):
        self.selected_course = selected_course
        self.lessons = lessons
        self.selected_lessons = selected_lessons


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


def handle_lessons_prompt(prompt_lessons, lessons):
    while True :
        selected_lessons = inquirer.prompt(prompt_lessons)['choices']

        if RETURN_TO_MAIN_MENU in selected_lessons:
            if len(selected_lessons) == 1:
                print("\n🔙 Returning to Main Menu...\n")
                break
            else:
                print("\n⚠️ You cannot select lessons and return at the same time. Please choose one option!\n")
        elif DOWNLOAD_ALL_LESSONS in selected_lessons:
            selected_lessons = lessons
            print(f"\n✅ All lessons will be downloaded: {', '.join(selected_lessons)}\n")
            break
        else:
            if selected_lessons:
                print(f"\n✅ You selected: {', '.join(selected_lessons)}\n")
                break
            else:
                print("\n⚠️ You must select at least one lesson. Try again!\n")
    return selected_lessons


def prompt_loop(session, courses):
    prompt_courses = [
        inquirer.List(
            'choice',
            message='Select a course (Press ↑/↓ to navigate, ENTER to confirm)',
            choices=courses.keys()
        )
    ]
    while True:
        selected_course = inquirer.prompt(prompt_courses)['choice']
        print(f"Retrieving lessons from {selected_course}...\n")
        lessons = get_lessons(session, courses[selected_course])
        special_options = [DOWNLOAD_ALL_LESSONS, RETURN_TO_MAIN_MENU]
        choices = special_options + list(lessons.keys())
        prompt_lessons = [
            inquirer.Checkbox(
                'choices',
                message='Select one or more lessons (Press ↑/↓ to navigate, SPACE to select/deselect, ENTER to confirm)',
                choices= choices
            )
        ]
        selected_lessons = handle_lessons_prompt(prompt_lessons, lessons)
        if selected_lessons != [RETURN_TO_MAIN_MENU]:
            return Prompt_outputs(selected_course, lessons, selected_lessons)


def main():
    tqdm.set_lock(threading.Lock())

    username = config['credentials']['username']
    password = config['credentials']['password']

    print("Logging in...\n")
    session = login(username, password)

    print("Retrieving courses...\n")
    courses = get_courses(session)

    prompt_result = prompt_loop(session, courses)
    print('Download will start shortly...\n')
    download_lessons(session, prompt_result.selected_course, prepend_index_to_lessons(filter_lessons(prompt_result.lessons, prompt_result.selected_lessons)))
    print(f"\nRecordings saved at {os.path.join(config['downloads']['folder'], clean_name(prompt_result.selected_course))}\n")


if __name__ == "__main__":
    main()
