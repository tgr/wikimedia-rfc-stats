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


class Api:
    endpoint = None

    def call(self, **params):
        return wikitools.api.APIRequest(self.endpoint, params).query(False)

    @classmethod
    def from_domain(cls, domain):
        api = Api()
        api.endpoint = wikitools.wiki.Wiki("http://%s/w/api.php" % domain)
        return api

    @classmethod
    def from_globaluserinfo_url(cls, url):
        api = Api()
        api.endpoint = wikitools.wiki.Wiki("%s/w/api.php" % url)
        return api

    def __call__(self, **params):
        return self.call(**params)


api = Api.from_domain(wiki)


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

def timestamp_to_datetime(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

def get_user_data(user):
    data = api(action='query',
                list='users|usercontribs',
                    ususers=user, usprop='editcount|groups|registration',
                    ucuser=user, ucdir='newer', uclimit=1, ucprop='timestamp',
                meta='globaluserinfo', guiuser=user, guiprop='editcount|groups|merged')['query']
    local_data = data['users'][0]
    global_data = data['globaluserinfo']
    first_local_edit = data['usercontribs'][0]['timestamp']

    merged = False
    for account in global_data['merged']:
        if account['wiki'] == 'commonswiki':
            merged = True
            break

    data = {
        'merged': False,
        'home_wiki': 'commonswiki',
        'local_edits': local_data['editcount'],
        'local_groups': local_data['groups'],
        'global_edits': local_data['editcount'],
        'global_groups': local_data['groups'],
        'first_local_edit': timestamp_to_datetime(first_local_edit),
        'first_global_edit': timestamp_to_datetime(first_local_edit),
    }

    if merged:
        data['merged'] = True
        data['home_wiki'] = global_data['home']
        data['global_edits'] = global_data['editcount']
        first_global_edit = None
        global_groups = []
        for account in global_data['merged']:
            print account['url']
            account_api = Api.from_globaluserinfo_url(account['url'])
            account_data = account_api(action='query', list='users|usercontribs',
                                        ususers=user, usprop='groups',
                                        ucuser=user, ucdir='newer', uclimit=1, ucprop='timestamp')['query']
            global_groups.extend(account_data['users'][0]['groups'])
            for edit in account_data['usercontribs']:
                first_account_edit = timestamp_to_datetime(edit['timestamp'])
                if not first_global_edit or first_account_edit < first_global_edit:
                    first_global_edit = first_account_edit
                break

        data['first_global_edit'] = first_global_edit

    return data


def get_local_gap(user):
    return api(action='query', list='usercontribs', ucuser=user, ucdir='older', uclimit=500, ucprop='title|timestamp')


i = 0
for vote in []:#get_votes():
    i = i + 1
    if i > 0:
        break

print get_user_data('Tgr')
