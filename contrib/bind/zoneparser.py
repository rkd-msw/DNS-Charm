import logging
import os
import random
import subprocess
import string
import tldextract
from .zone import Zone

import ipdb

# Note about how this is constructed. BIND ships with a tool called
# named-checkzone. This normalizes ALL output from a bind file, and
# allows this class to make some assumptions about placement of values.
# Anything loaded from file here will be passed through this utility.
# If it fails to normalize/parse the file, then the operation will fail.

# I'm open to suggestions on how to do this outside of relying on bind's
# wrapping normalizer

logging.basicConfig(level=logging.INFO)


class ZoneParser(object):

    def __init__(self, domain, file_handle=None):
        self.zone = Zone()
        self.domain = domain
        self.implemented_records = self.zone.contents.keys()
        self.tldxtr = tldextract.extract
        if file_handle:
            self.load_and_parse(file_handle)
        # Todo handle if file exists

    def load_and_parse(self, filepath):
        self.zonefile = filepath
        self.contents = self.from_file(filepath)
        self.array_to_zone()

    def from_file(self, file_handle):
        contents = []
        normalized_file = self.normalize_contents(file_handle)
        with open(normalized_file) as f:
            for line in f.readlines():
                contents.append(line)
        return contents

    def save(self, outpath='/etc/bind'):
        self.zone.to_file(outpath=outpath, domain=self.domain)

    # ####################################
    # Utility Methods
    # ####################################

    def locate_zone(self, filepath):
        if not os.path.exists(filepath):
            open('/etc/bind/db.%s' % self.domain, 'a').close()
            return "/etc/bind/db.%s" % self.domain
        else:
            return filepath

    # Create an intermediate file to warehouse the normalized config
    def normalize_contents(self, file_handle):
        if os.path.exists(file_handle):
            rando = self.id_generator(8)
            rando_filepath = "/tmp/%s" % rando
            subprocess.call(['named-checkzone', '-o', rando_filepath,
                             self.domain, file_handle])
            logging.info('created temporary file %s' % rando_filepath)
            return rando_filepath

    def __validate_attributes(self, configuration):
            if configuration['type'] not in self.implemented_records:
                raise KeyError("Unknown key %s" % configuration['type'])

    def id_generator(self, size=6):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(size))

    def __is_path(self, file_handle):
        if os.path.sep in file_handle:
            return True
        return False

    # #######################################
    # Parsing Array to Zone Dictionary - this is going
    # to be a bit messy, and specific to loading
    # from the named-checkzone utility - this is brittle
    # #######################################

    def failed_check(self):
            raise IndexError("Array Notation should conform to named-checkzone"
                             " specification")

    def a_from_array(self, data):
        if len(data) < 6:
            self.failed_check()
        ttl = data[4].strip().split(' IN')[0]
        addr = data[6].strip()
        try:
            alias = self.tldxtr(data[0].strip()).subdomain
        except:
            alias = "@"
        parsed = {'ttl': ttl, 'addr': addr, 'alias': alias}
        self.zone.a(parsed)

    def aaaa_from_array(self, data):
        if len(data) < 6:
            self.failed_check()
        ttl = data[4].strip().split(' IN')[0]
        addr = data[6].strip()
        try:
            alias = self.tldxtr(data[0].strip()).subdomain
        except:
            alias = "@"
        parsed = {'ttl': ttl, 'addr': addr, 'alias': alias}
        self.zone.aaaa(parsed)

    def cname_from_array(self, data):
        if len(data) < 6:
            self.failed_check()
        alias = self.tldxtr(data[0].strip()).subdomain
        ttl = data[4].strip().split(' IN')[0]
        addr = data[6].strip()
        parsed = {'ttl': ttl, 'addr': addr, 'alias': alias}
        self.zone.cname(parsed)

    def ns_from_array(self, data):
        if len(data) < 6:
            self.failed_check()
        ttl = data[4].strip().split(' IN')[0]
        owner_name = "%s." % self.domain
        alias = data[6].strip()
        parsed = {'ttl': ttl, 'alias': alias, 'owner-name': owner_name}
        self.zone.ns(parsed)

    def soa_from_array(self, data):
        if len(data) < 6:
            self.failed_check()
        agg = data[6].strip().split(' ')
        logging.info("agg: %s" % agg)
        ttl = data[4].strip().split(' IN')[0]
        addr = agg[0]
        alias = agg[1]
        serial = agg[2]
        refresh = agg[3]
        try:
            update_retry = agg[4]
        except:
            update_retry = None
        try:
            expiry = agg[5]
        except:
            expiry = None
        try:
            minimum = agg[6]
        except:
            minimum = None
        parsed = {'ttl': ttl, 'addr': addr, 'alias': alias, 'serial': serial,
                  'refresh': refresh, 'update-retry': update_retry,
                  'expiry': expiry, 'minimum': minimum}
        self.zone.soa(parsed)

    def array_to_zone(self):
        if not self.contents:
            raise ValueError("Missing Zone Contents")

        for entry in self.contents:
            line = entry.split('\t')
            dclass = line[5].strip()
            for case in switch(dclass):
                if case('A'):
                    self.a_from_array(line)
                    break
                if case('AAAA'):
                    self.aaaa_from_array(line)
                    break
                if case('CNAME'):
                    self.cname_from_array(line)
                    break
                if case('NS'):
                    self.ns_from_array(line)
                    break
                if case('SOA'):
                    self.soa_from_array(line)
                    break
                if case():
                    pass
                    logging.warning('Unable to match type %s' % dclass)


# Python doesn't give us a switch case statement, so replicate it here.
class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:
            self.fall = True
            return True
        else:
            return False
