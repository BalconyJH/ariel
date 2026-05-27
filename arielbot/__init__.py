import json
from os import getcwd, mkdir, path

import click
import dotenv
import nonebot


env = {
    "DRIVER": "~fastapi+~httpx+~websockets",
    "SUPERUSERS": [],
    "HOST": "127.0.0.1",
    "PORT": 12315,
    "COMMAND_START": ["/"],
    "SENTRY_DSN": "",
    "SENTRY_TRACES_SAMPLE_RATE": 0.0,
    "SENTRY_PROFILES_SAMPLE_RATE": 0.0,
    "SENTRY_PROFILE_SESSION_SAMPLE_RATE": 0.0,
    "SENTRY_PROFILE_LIFECYCLE": "trace",
    "SENTRY_ENABLE_LOGS": False,
    "SENTRY_SEND_DEFAULT_PII": False,
    "MILKY_CLIENTS": [
        {
            "host": "lagrange-milky",
            "port": 3000,
            "access_token": "",
            "secure": False,
        }
    ],
}


@click.group()
def main():
    pass


@click.command()
def run():
    create_config()
    create_plugins_dir()
    from .bot import app
    nonebot.run(app=app)


main.add_command(run)


def create_config():
    env_file_path = path.join(getcwd(), ".env.prod")
    if not path.exists(env_file_path):
        for key, value in env.items():
            dotenv.set_key(
                env_file_path,
                key,
                json.dumps(value, separators=(",", ":")),
                quote_mode="never"
            )


def create_plugins_dir():
    plugins_dir_path = path.join(getcwd(), "plugins")
    if not path.exists(plugins_dir_path):
        mkdir(plugins_dir_path)


