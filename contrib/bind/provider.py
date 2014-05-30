import os
import subprocess
import sys
from .zoneparser import ZoneParser
from random import randint

# Add charmhelpers to the system path.
try:
    sys.path.insert(0, os.path.abspath(os.path.join(os.environ['CHARM_DIR'],
                                                    'lib')))
except:
    sys.path.insert(0, os.path.abspath(os.path.join('..', '..', 'lib')))

from charmhelpers.core.hookenv import open_port, unit_get
from charmhelpers.core.host import service_reload

from charmhelpers.fetch import (
    apt_install,
    apt_update,
)


class BindProvider(object):

    def install(self):
        apt_update(fatal=True)
        apt_install(packages=[
            'bind9',
            'dnsutils',
            ], fatal=True)
        open_port(53)

    def config_changed(self, domain='example.com'):
        zp = ZoneParser(domain)
        # Install a skeleton bind zone, rehashes existing file
        # if it has contents)
        if not os.path.exists('/etc/bind/db.%s' % domain):
            self.first_setup(zp, domain)
            zp.save()
            self.reload_config()

    def add_record(self, record, domain='example.com'):
        zp = ZoneParser(domain)
        zp.dict_to_zone(record)
        zp.save()
        self.reload_config()

    def remove_record(self, record, domain='example.com'):
        zp = ZoneParser(domain)
        zp.zone.remove(record['rr'], 'alias', record['alias'])
        zp.save()
        self.reload_config()

    def first_setup(self, parser, domain='example.com'):
        # Insert SOA and NS records
        addr = unit_get('public-address')
        parser.dict_to_zone({'rr': 'SOA',
                             'addr': 'ns.%s.' % domain,
                             'owner': 'root.%s.' % domain,
                             'serial': randint(12345678, 22345678),
                             'refresh': '12h',
                             'update-retry': '15m',
                             'expiry': '3w',
                             'minimum': '3h'})
        parser.dict_to_zone({'rr': 'NS', 'alias': '@',
                             'addr': 'ns1.%s.' % domain})
        parser.dict_to_zone({'rr': 'A', 'alias': '@', 'addr': addr,
                             'ttl': 300})
        parser.dict_to_zone({'rr': 'A', 'alias': 'ns1', 'addr': addr,
                             'ttl': 300})
        parser.dict_to_zone({'rr': 'CNAME', 'alias': 'ns',
                             'addr': 'ns1.example.com.', 'ttl': 300})

    def reload_config(self):
        service_reload('bind9')
