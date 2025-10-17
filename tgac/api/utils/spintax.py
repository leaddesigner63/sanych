import random
import re

SPIN_PATTERN = re.compile(r"\{([^{}]+)\}")


def spin(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        options = match.group(1).split("|")
        return random.choice(options)

    while True:
        if not SPIN_PATTERN.search(text):
            return text
        text = SPIN_PATTERN.sub(replace, text)
