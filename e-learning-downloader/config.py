import argparse
import configparser
import os

CONFIG_FILE_PATH = 'config.ini'
config = {
    'credentials': {},
    'downloads': {},
    'args': {}
}

def load_config():
    cp = configparser.ConfigParser()
    cp.read(CONFIG_FILE_PATH)

    # CREDENTIALS
    config['credentials']['username'] = cp.get('credentials', 'username')
    config['credentials']['password'] = cp.get('credentials', 'password')

    # DOWNLOADS
    folder = cp.get('downloads', 'folder', fallback='Downloads')
    if os.path.isabs(folder):
        config['downloads']['folder'] = folder
    else:
        config['downloads']['folder'] = os.path.abspath(folder)

    # ARGUMENTS
    args = load_arguments()
    config['args']['skip_optional_recordings'] = args.skip_optional_recordings
    config['args']['skip_attachments'] = args.skip_attachments


def load_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-optional-recordings', action='store_true', help='ignores optional recordings')
    parser.add_argument('--skip-attachments', action='store_true', help='ignores attachments')
    args = parser.parse_args()
    return args


load_config()

