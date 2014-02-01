"""
Configuration settings. These should be in a file called config.py
"""

# Domain name of the wiki.
wiki = 'example.com'

# Page which contains the RFC.
page = 'Project:RFC/Some RFC'

# Which revision of the page to use (None means current)
revision = None

# Relevant sections in this format:
# {
#     'foo': 1,
#     'bar': 3,
# }
# The name will be used in the output to identify what the user voted for.
# The number is the same one you see in the section edit link.
sections = {
}

# date format in signature
# you only need to change these for non-English wikis
date_format = '%H:%M, %d %B %Y (UTC)'
date_regexp = r'\d{2}:\d{2}, \d{1,2} %s \d{4} \(UTC\)' \
              % '(January|February|March|April|May|June|July|August|September|October|November|December)'
# date locale might be OS-dependent; use locale -a to list supported locales
date_locale = 'en_US.utf8'
