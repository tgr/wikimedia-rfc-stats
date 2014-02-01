#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Calculates participant statictics for MediaWiki RFC-s/votes/etc.

Assumptions:
* RFC is on a single page, with each position having its own section
* every vote starts with # (numbered list item) - other lines (including those starting with ##, #: etc) are ignored
* first userpage/talkpage link in the line is that of the voter (this will fail sometimes, but hopefully not often
  enough to throw off the results)
* first date string in the line is the time of the vote

Usage:
* install dependencies with pip install -r requirements.txt
* copy config.dist.py to config.py, edit settings
* run rfc_stats.py
"""

import re, locale, itertools
from datetime import datetime
import wikitools

from config import wiki, page, revision, sections, date_format, date_locale, date_regexp

endpoint = wikitools.wiki.Wiki("http://%s/w/api.php" % wiki)

locale.setlocale(locale.LC_TIME, date_locale)


class Vote:
    """Data about a single vote"""

    vote = None
    """One of the section labels"""

    text = None
    """Full text of the vote"""

    username = None
    """Username without the User: prefix"""

    datetime = None
    """datetime object with the time of the vote"""

    first_local_edit_date = None
    """when did the user edit first on the wiki where the RFC took place?"""

    first_global_edit_dare = None
    """when did the user edit first, anywhere?"""

    local_edits = None
    """edit count on the wiki where the RFC took place"""

    global_edits = None
    """global edit count"""

    is_local_admin = None
    """is the user an admin (bureaucrat, steward etc) on the wiki where the RFC took place?"""

    is_global_admin = None
    """is the user an admin (bureaucrat, steward etc) anywhere?"""

    local_gap = None
    """time spent inactive on the local wiki before the RFC (months, rounded down)"""

    global_gap = None
    """time spent inactive everywhere before the RFC (months, rounded down)"""

    @classmethod
    def from_line(cls, line, section_label):
        vote = Vote()
        vote.vote = section_label
        vote.text = line
        vote.username = Vote.get_username(line)
        vote.datetime = Vote.get_datetime(line)

        user_data = get_user_data(vote.username)
        return vote

    @classmethod
    def get_username(cls, line):
        m = re.search(r'\[\[User(?:_talk)?:([^|\]]+)', line)
        if m:
            return m.group(1)

    @classmethod
    def get_datetime(cls, line):
        m = re.search(date_regexp, line)
        if m:
            return datetime.strptime(m.group(0), date_format)

    def __str__(self):
        return str(self.__dict__)


def chunks(list, size):
    chunk = []
    list = iter(list)
    try:
        for i in range(size):
            chunk.append(next(list))
    except StopIteration:
        if len(chunk) > 0:
            yield chunk
        return

    yield chunk


def api(**params):
    return wikitools.api.APIRequest(endpoint, params).query()

def get_section_text(section):
    params = {
        'action': 'query',
        'prop': 'revisions',
        'rvsection': section,
        'rvprop': 'content'
    }
    if revision:
        params['revids'] = revision
    else:
        params['titles'] = page
    for p in api(**params)['query']['pages'].values():
        for r in p['revisions']:
            return r['*']

def get_vote_lines(section):
    for line in get_section_text(section).splitlines():
        if re.match(r'#[^#*:]', line):
            yield line

def get_votes():
    for section_label, section_id in sections.items():
        for line in get_vote_lines(section_id):
            yield Vote.from_line(line, section_label)

def get_user_data(user):
    data = api(action='query',
                list='users',
                    ususers=user, usprop='editcount|groups',
                meta='globaluserinfo', guiuser=user, guiprop='editcount|groups')['query']
    local_data = data['users'][0]
    global_data = data['globaluserinfo']
    data = api(action='query',
                list='usercontribs',
                    ucuser=user, ucdir='newer', uclimit=1, ucprop='timestamp')['query']
    return data, local_data, global_data

def get_local_first_contrib(user):
    return api(action='query', list='usercontribs', )

def get_local_gap(user):
    return api(action='query', list='usercontribs', ucuser=user, ucdir='older', uclimit=500, ucprop='title|timestamp')


i = 0
for vote in []:#get_votes():
    i = i + 1
    if i > 0:
        break

print get_user_data('Tgr')
