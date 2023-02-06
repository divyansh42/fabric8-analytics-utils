#!/usr/bin/env python3
# Copyright © 2020 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Author: Yusuf Zainee <yzainee@redhat.com>
#

"""Utility file to fetch github details."""

import re
import random
import logging
import requests
from os import environ
from datetime import datetime
import base64
from requests.exceptions import ConnectionError
import time

_logger = logging.getLogger(__name__)

msg = "ZTI4YTBkMGUxMjM4YWY1NmJhZGEzN2U4NjJjMDQwZGY2MDlkYzZiYSw5NWNhO" \
      "DliMzM0OWMwMWY0NDEzMGU3NTk4YjUwMzJlNjNmMjk5M2Nm"


class GithubUtils:
    """Github utils class."""

    def __init__(self):
        """Init method for GithubUtils class."""
        self.GITHUB_TOKEN = environ.get('GITHUB_TOKEN', "")
        self.GITHUB_API = "https://api.github.com/"
        base64_bytes = msg.encode('ascii')
        msg_bytes = base64.b64decode(base64_bytes)
        message = msg_bytes.decode('ascii')
        if not self.GITHUB_TOKEN:
            self.GITHUB_TOKEN = message
        self.GITHUB_TOKEN = self.GITHUB_TOKEN.split(",")

    def __select_gh_token(self):
        """Randomly select and return a gh token."""
        if len(self.GITHUB_TOKEN) > 0:
            return random.choice(self.GITHUB_TOKEN)
        _logger.info("Could not select a gh token.")
        return None

    def __make_get_call(self, url, iter=0):
        """Make an api call and return results."""
        token = self.__select_gh_token()
        headers = None
        if token:
            headers = {
                'Authorization': 'token {t}'.format(t=token)
            }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                _logger.error("Error Code: {}".format(response.status_code))
                return None
        except ConnectionError as e:
            _logger.error("Exception while trying to make an API call {}".format(e))
            iter += 1
            time.sleep(iter)
            if iter <= 3:
                return self.__make_get_call(url, iter)
            else:
                return None
        except Exception as e:
            _logger.error("Exception while trying to make an API call {}".format(e))
            return None
        return response.json()

    def _get_verion_list(self, org, name):
        """Return a the list of release versions."""
        ver_list = []
        try:
            assert org
            assert name
        except AssertionError as e:
            _logger.error("Input data is not valid. {}".format(e))
            return None
        url = self.GITHUB_API + "repos/{o}/{n}/tags".format(
            o=org, n=name)

        data = self.__make_get_call(url)
        if not data or len(data) == 0:
            _logger.info("No tags found for the url {}".format(url))
            return None
        for tag in data:
            url = tag['url']
            if url and 'tags/' in url:
                ver = url.split('tags/')[1]
                if ver.startswith('v'):
                    ver = ver.split('v')[1]
                ver_list.append(ver)
        return ver_list

    def _get_hash_from_semver(self, org, name, version):
        """Return the commit hash from the semver."""
        try:
            assert org
            assert name
            assert version
        except AssertionError as e:
            _logger.error("Input data is not valid. {}".format(e))
            return None
        url = self.GITHUB_API + "repos/{o}/{n}/git/refs/tags/{v}".format(
            o=org, n=name, v=version)

        data = self.__make_get_call(url)
        if not data:
            _logger.info("No commit hash found for the url {}".format(url))
            return None
        sha = data.get('object', {}).get('sha', '')
        return sha

    def _get_date_from_commit_sha(self, org, name, sha):
        """Return the commit date for the commit hash."""
        try:
            assert org
            assert name
            assert sha
        except AssertionError as e:
            _logger.error("Input data is not valid. {}".format(e))
            return None
        url = self.GITHUB_API + "repos/{o}/{n}/commits/{s}".format(
            o=org, n=name, s=sha)

        data = self.__make_get_call(url)
        if not data:
            _logger.info("No details found for the url {}".format(url))
            return None
        commit = data.get('commit', {})
        if commit:
            date = commit.get('committer', {}).get('date', '')
        else:
            date = None
        return date

    def _get_date_from_tag_sha(self, org, name, sha):
        """Return the commit tag date for the tag hash."""
        try:
            assert org
            assert name
            assert sha
        except AssertionError as e:
            _logger.error("Input data is not valid. {}".format(e))
            return None

        url = self.GITHUB_API + "repos/{o}/{n}/git/tags/{s}".format(
            o=org, n=name, s=sha)
        data = self.__make_get_call(url)
        if not data:
            _logger.info("No details found for the url {}".format(url))
            return None
        date = data.get('tagger', {}).get('date', '')
        return date

    def _get_date_from_semver(self, org, name, version):
        """Get the commit date from the version."""
        tag_sha = self._get_hash_from_semver(org, name, version)
        if not tag_sha:
            _logger.info("Not able to fetch details for the version.")
            return None
        dt = self._get_date_from_commit_sha(org, name, tag_sha)
        if not dt:
            dt = self._get_date_from_tag_sha(org, name, tag_sha)
        return dt

    def _get_commit_date(self, org, name, commit_data):
        """Get the commit date details from the tag or hash."""
        if len(commit_data) == 40:
            # chances are that its a commit hash
            dt = self._get_date_from_commit_sha(org, name, commit_data)
            if not dt:
                dt = self._get_date_from_tag_sha(org, name, commit_data)
            if dt:
                return dt
        dt = self._get_date_from_semver(org, name, commit_data)
        return dt

    def __check_for_date_rule(self, comm_date, date_rule):
        """Check if the committed date falls in the date rule."""
        if date_rule == "*":
            return True
        if '&' in date_rule:
            date_rules_splitted = date_rule.split('&')
            return self.__check_for_date_rule(comm_date, date_rules_splitted[0]) and \
                self.__check_for_date_rule(comm_date, date_rules_splitted[1])
        operator = date_rule.split('#')[0]
        operand = datetime.strptime(date_rule.split('#')[1], '%Y-%m-%dT%H:%M:%SZ')
        if operator == "<":
            return comm_date < operand
        elif operator == "<=":
            return comm_date <= operand
        elif operator == ">":
            return comm_date > operand
        elif operator == ">=":
            return comm_date >= operand
        elif operator == "=":
            return comm_date == operand
        else:
            return False

    def _is_commit_in_vuln_range(self, org, name, sha, date_range_rules):
        """Return True or False if the date of commit sha lies within the vuln date range rules."""
        """
        rules can be provided in the following format:
        >#2020-09-17T13:19:13Z,>=#2020-09-17T13:19:13Z&<2020-09-20T13:19:13Z and so on.
        """
        comm_date = self._get_date_from_commit_sha(org, name, sha)
        if not comm_date:
            comm_date = self._get_date_from_tag_sha(org, name, sha)
        if not comm_date:
            _logger.info("No info on the commit hash {h} for {o}/{n} found.".format(
                h=sha, o=org, n=name
            ))
            return None
        comm_date = datetime.strptime(comm_date, '%Y-%m-%dT%H:%M:%SZ')
        if ',' in date_range_rules:
            rules = date_range_rules.split(',')
            for rule in rules:
                val = self.__check_for_date_rule(comm_date, rule)
                if val:
                    return True
            return False
        else:
            return self.__check_for_date_rule(comm_date, date_range_rules)

    def _is_commit_date_in_vuln_range(self, date_string, date_range_rules):
        """Return True or False if the date of commit sha lies within the date range rules."""
        """
        rules can be provided in the following format:
        >#2020-09-17T13:19:13Z,>=#2020-09-17T13:19:13Z&<2020-09-20T13:19:13Z and so on.
        date in yyyymmddhhmmss format.
        """
        try:
            comm_date = datetime.strptime(date_string, '%Y%m%d%H%M%S')
        except ValueError:
            _logger.error("Date format is wrong. Follow yyyymmddhhmmss format")
            return None
        if ',' in date_range_rules:
            rules = date_range_rules.split(',')
            for rule in rules:
                val = self.__check_for_date_rule(comm_date, rule)
                if val:
                    return True
            return False
        else:
            return self.__check_for_date_rule(comm_date, date_range_rules)

    def is_pseudo_version(self, pseudo_version):
        """Check if given version is a pseudo version.

        :param version: str - Package version.
        :return: True is its pseudo version for golang otherwise False.
        """
        # Pseudo if contains semver followed by 14 digit timestamp and 12 digits commit hash.
        # Example :: v0.0.0-20200410000936-a663fba25f7a
        return len(re.findall(r'\d.\d.\d-\d{14}-[0-9a-zA-Z]{12}', pseudo_version)) == 1

    def extract_timestamp(self, pseudo_version: str):
        """Extract timestamp value YYYYMMDDHHMMSS from given string."""
        # Example :: v0.0.0-20200410000936-a663fba25f7a
        timestamp = re.findall(r'\d{14}', pseudo_version)
        if len(timestamp) > 0:
            return str(timestamp[0])

        return None
