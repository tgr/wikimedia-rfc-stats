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

import re
import locale
from datetime import datetime
import wikitools
import csv

import config

locale.setlocale(locale.LC_TIME, config.date_locale)


class Vote:
    """Data about a single vote"""

    def __init__(self):
        self.section_label = None
        """
        @type: str
        One of the section labels
        """

        self.text = None
        """
        @type: str
        Full text of the vote
        """

        self.user = None
        """
        @type: User
        """

        self.datetime = None
        """
        time of the vote
        @type : datetime.datetime
        """

        self.local_gap = None
        """time spent inactive on the local wiki before the RFC (months, rounded down)"""

        self.global_gap = None
        """time spent inactive everywhere before the RFC (months, rounded down)"""

    def __str__(self):
        return str(self.to_dict())

    def to_dict(self):
        self_dict = self.__dict__
        if self_dict['user']:
            self_dict['user'] = self_dict['user'].to_dict()
        return self_dict

    @classmethod
    def from_line(cls, page, line, section_label):
        """
        Creates a Vote from a line of text (which should contain a signature). There is no sanity check done
        to see if it is indeed a vote.
        @type page: VotePage
        @type line: str
        @type section_label: str
        @rtype: Vote
        """
        vote = cls()
        vote.section_label = section_label
        vote.text = line
        vote.datetime = cls.get_datetime(line)

        username = cls.get_username(line)
        vote.user = User(page.api, username)
        vote.user.load_data()

        return vote

    @staticmethod
    def get_username(line):
        """
        @type line: str
        @rtype: str
        """
        m = re.search(r'\[\[User(?:_talk)?:([^|\]]+)', line)
        if m:
            return m.group(1)

    @staticmethod
    def get_datetime(line):
        """
        @type line: str
        @rtype: str
        """
        m = re.search(config.date_regexp, line)
        if m:
            return datetime.strptime(m.group(0), config.date_format)

    @staticmethod
    def filter_vote_lines(lines):
        """
        Iterates through a set of lines and only returns those which seem to be votes (top-level ordered lists).
        @type lines: collections.Iterable[string]
        """
        for line in lines:
            if re.match(r'#[^#*:]', line):
                yield line

    def get_plaintext(self):
        return re.sub(r'<.*?>', '', self.text)


class Api:
    endpoint = None
    """@type wikitools.wiki.Wiki"""

    def __init__(self, endpoint):
        """
        @type endpoint: wikitools.wiki.Wiki
        """
        assert isinstance(endpoint, wikitools.wiki.Wiki)
        self.endpoint = endpoint

    @classmethod
    def from_domain(cls, domain):
        """
        @type domain: string
        @rtype: Api
        """
        return cls(wikitools.wiki.Wiki("http://%s/w/api.php" % domain))

    @classmethod
    def from_globaluserinfo_url(cls, url):
        """
        @type url: string
        @rtype: Api
        """
        return cls(wikitools.wiki.Wiki("%s/w/api.php" % url))

    @staticmethod
    def timestamp_to_datetime(timestamp):
        """
        @type timestamp: string
        @rtype: datetime.datetime
        """
        return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def chunks(seq, size):
        """
        Chops a list or iterable into segments.
        @type seq: list
        @type size: int
        """
        chunk = []
        seq = iter(seq)
        try:
            for i in range(size):
                chunk.append(next(seq))
        except StopIteration:
            if len(chunk) > 0:
                yield chunk
            return

        yield chunk

    def call(self, **params):
        """
        Makes a call to the API. Pass API parameters as function parameters: api.call(action='query', list='users', ...
        @rtype: dict
        """
        return wikitools.api.APIRequest(self.endpoint, params).query(False)

    def __call__(self, **params):
        return self.call(**params)

    def get_section_text(self, page=None, revision=None, section=None):
        """
        Returns the text of the specified section. section is required; one of page and revision is required.
        @type page: str
        @type revision: int
        @type section: int
        @rtype: str
        """
        if not section or not page and not revision:
            raise ValueError('section and either page or revision is required')

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
        for p in self(**params)['query']['pages'].values():
            for r in p['revisions']:
                return r['*']


class VotePage:
    def __init__(self, api, page=None, revision=None, sections=None):
        """
        @type api: Api
        @type page: str
        @type revision: int
        @type sections: dict[str, int]
        """
        if not sections or not page and not revision:
            raise ValueError('sections and either page or revision is required')

        self.api = api
        """@type: Api"""

        self.page = page
        """
        Page name (ignored if there is a revision id)
        @type: str
        """

        self.revision = revision
        """
        Revision id to analyze, None for current
        @type: int
        """

        self.sections = sections
        """
        Section ids and internal labels (will be used in the output)
        @type: dict[str, int]
        """

    def get_page_arg(self):
        arg = {}
        if self.revision:
            arg['revision'] = self.revision
        else:
            arg['page'] = self.page
        return arg

    def get_vote_lines(self, section):
        """
        @type section: int
        """
        args = self.get_page_arg()
        args['section'] = section
        all_lines = self.api.get_section_text(page=self.page, revision=self.revision, section=section).splitlines()
        for line in Vote.filter_vote_lines(all_lines):
            yield line

    def get_votes(self, section=None, limit=None):
        """
        @type section: int|str
        @param section: limit votes to a single section
        @type limit: int
        @param limit: only return a limited number of votes
        """
        i = 0
        for section_label, section_id in self.sections.items():
            if section and section_label != section and section_id != section:
                continue
            for line in self.get_vote_lines(section_id):
                i += 1
                yield Vote.from_line(self, line, section_label)
                if i == limit:
                    return


class GlobalUser:
    def __init__(self, username):
        """
        @type username: str
        """

        self.username = username
        """
        @type str
        """

        self.home_wiki = None
        """
        Home wiki db name (enwiki, frsource etc)
        @type: str
        """

        self.wikis = None
        """
        List of wiki db names where the user has an account
        @type: list[str]
        """

        self.wiki_urls = None
        """
        List of wiki URLs (schema + domain, no trailing slash) where the user has an account
        @type: list[str]
        """

        self.editcount = None
        """
        @type: int
        """

        self.groups = None
        """
        A union of all the group roles held at some wiki
        @type: list[str]
        """

        self.first_edit = None
        """
        @type: datetime.datetime
        """

    def __str__(self):
        return str(self.to_dict())

    def to_dict(self):
        self_dict = self.__dict__
        del self_dict['wikis']
        del self_dict['wiki_urls']
        return self_dict

    @classmethod
    def from_globaluserinfo(cls, username, global_data):
        """
        @type username: str
        @type global_data: dict
        """
        user = cls(username)
        user.home_wiki = global_data['home']
        user.editcount = global_data['editcount']
        user.wikis = []
        user.wiki_urls = []

        for account in global_data['merged']:
            user.wikis.append(account['wiki'])
            user.wiki_urls.append(account['url'])

        return user

    def load_data(self):
        self.groups = []
        for url in self.wiki_urls:
            api = Api.from_globaluserinfo_url(url)
            data = api(action='query', list='users|usercontribs',
                                   ususers=self.username, usprop='groups',
                                   ucuser=self.username, ucdir='newer', uclimit=1, ucprop='timestamp')['query']

            self.groups.extend(data['users'][0]['groups'])
            if len(data['usercontribs']):
                first_edit_on_this_wiki = Api.timestamp_to_datetime(data['usercontribs'][0]['timestamp'])
                if not self.first_edit or first_edit_on_this_wiki < self.first_edit:
                    self.first_edit = first_edit_on_this_wiki


class User:
    def __init__(self, api, username):
        """
        @type api: Api
        @param api: Api object to the user's wiki
        """

        self.api = api
        """@type: Api"""

        self.username = username
        """Username without the User: prefix"""

        self.global_user = None
        """
        None means uninitialized, False means not attached.
        @type: GlobalUser
        """

        self.editcount = None
        """
        @type: int
        """

        self.groups = None
        """
        @type: list[str]
        """

        self.first_edit = None
        """
        @type: datetime.datetime
        """

    def __str__(self):
        return str(self.to_dict())

    def to_dict(self):
        self_dict = self.__dict__
        if self_dict['global_user']:
            self_dict['global_user'] = self_dict['global_user'].to_dict()
        return self_dict

    def is_admin(self):
        return 'sysop' in self.groups

    def load_data(self, data=None):
        if not data:
            data = self.api(action='query',
                            list='users|usercontribs',
                                ususers=self.username, usprop='editcount|groups|registration',
                                ucuser=self.username, ucdir='newer', uclimit=1, ucprop='timestamp',
                            meta='globaluserinfo', guiuser=self.username, guiprop='editcount|groups|merged')['query']
        local_data = data['users'][0]
        global_data = data['globaluserinfo']
        first_local_edit = data['usercontribs'][0]['timestamp']

        self.groups = local_data['groups']
        self.editcount = local_data['editcount']
        self.first_edit = Api.timestamp_to_datetime(first_local_edit)

        if self.data_is_global(global_data):
            self.global_user = GlobalUser.from_globaluserinfo(self.username, global_data)
            #self.global_user.load_data()
        else:
            self.global_user = False

    def data_is_global(self, global_data):
        merged = False
        if 'merged' in global_data:
            for account in global_data['merged']:
                if account['wiki'] == 'commonswiki':
                    merged = True
                    break
        return merged

    def get_local_gap(self, user):
        data = self.api(action='query',
                        list='usercontribs', ucuser=self.username, ucdir='older', uclimit=500, ucprop='title|timestamp')

    def get_global_editcount(self):
        if self.global_user:
            return self.global_user.editcount
        else:
            return None

    def get_home_wiki(self):
        if self.global_user:
            return self.global_user.home_wiki
        else:
            return None


vote_page = VotePage(Api.from_domain(config.wiki), page=config.page, revision=config.revision, sections=config.sections)
