"""
device_detector Test Cases. Run entire suite by:

python3 -m unittest

Run individual test class by:

python3 -m unittest device_detector.tests.parser.test_bot
"""
import unittest
import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

from ..settings import ROOT
from .. import DeviceDetector

# App names -> Application ID map so that upstream
# test fixtures can pass without modifications
APPID_TO_NAME = {
    'com.google.GooglePlus': 'Google Plus',
    'com.google.android.youtube': 'YouTube',
    'com.google.android.apps.magazines': 'Google Play Newsstand',
}


class Base(unittest.TestCase):

    fixture_files = []
    Parser = None

    def assertEqual(self, first, second, msg=None):
        if first == 'None':
            first = None
        if second == 'None':
            second = None
        # Count all falsy types as equal
        if not first and not second:
            return

        if not msg and hasattr(self, 'user_agent'):
            msg = '\n\nFailed to parse "{}"\n' \
                  'Expected value "{}" != Parsed value "{}"'.format(
                getattr(self, 'user_agent'), first, second,
            )

        super().assertEqual(first, second, msg)

    def load_fixtures(self):
        fixtures = []
        for ffile in self.fixture_files:
            with open('{}/{}'.format(ROOT, ffile), 'r') as r:
                fixtures.extend(yaml.load(r, SafeLoader))
        return fixtures


class DetectorBaseTest(Base):
    Parser = DeviceDetector

    def confirm_client_name(self, fixture, parsed_name):
        """
        Client name may be specified as empty string in Matomo
        regexes, but we want to extract a generic name from the
        beginning of the regex.

        :parsed_name: The name the parser extracted
        """
        fixture_name = self.get_value(fixture, 'client', 'name')

        # if there's a fixture name, then the parsed value should match
        if fixture_name:
            self.assertEqual(fixture_name, parsed_name)

        else:
            # but if no fixture name specified, then generic parsed name
            # should be taken from the beginning of the UA string
            for value in (parsed_name, parsed_name.replace(' ', '')):
                if self.user_agent.startswith(value):
                    return

            self.assertTrue(
                self.user_agent.startswith(parsed_name),
                msg='%s does not start with %s' % (self.user_agent, parsed_name),
            )

    def confirm_client_type(self, fixture, parsed_value):
        """
        Matomo will call many more apps "browsers" than we do.

        :parsed_value: The value the parser extracted
        """
        fixture_value = self.get_value(fixture, 'client', 'type')

        # like our name better...
        if fixture_value == 'browser' and fixture_value != parsed_value:
            return

        if fixture_value:
            self.assertEqual(str(fixture_value), str(parsed_value))

    def confirm_version(self, fixture, parsed_value):
        """
        If fixture data is empty, make sure the version string
        is a substring of the user agent.

        :parsed_value: The value the parser extracted
        """
        fixture_value = self.get_value(fixture, 'client', 'version')

        # if the fixture value specifies a version, it should match
        # otherwise, skip checking. The generic version extractor
        # will push/pull values a bit.
        if fixture_value:
            self.assertEqual(str(fixture_value), str(parsed_value))

    def matches_fixture_or_generic(self, fixture, key1, key2, parsed_value):
        """
        If fixture data is empty, allow the parsed_value to be "generic"
        which might be what our generic extractors return.

        :parsed_name: The name the parser extracted
        """
        fixture_value = self.get_value(fixture, key1, key2)

        if fixture_value:
            self.assertEqual(fixture_value, parsed_value)
        elif parsed_value:
            # check various generic values
            self.assertIn(parsed_value, ('generic', 'Windows', 'smartphone', 'XX'))

    def get_value(self, fixture, key1, key2):
        """
        Helper function to get values from keys, where keys may not exist

        :param fixture: The fixture dictionary of data that parsed data should match
        :param key1: The section of the fixture (client / os / device)
        :param key2: The key of the value to test
        """
        if not fixture:
            return ''

        if key1 not in fixture:
            return ''

        if not fixture[key1] or key2 not in fixture[key1]:
            return ''

        return str(fixture[key1][key2])

    def test_parsing(self):

        if not self.Parser:
            return

        for fixture in self.load_fixtures():
            self.user_agent = fixture.pop('user_agent')
            device = self.Parser(self.user_agent)
            device.parse()

            # OS properties
            self.assertEqual(device.os_name(), self.get_value(fixture, 'os', 'name'))
            self.assertEqual(device.os_short_name(), self.get_value(fixture, 'os', 'short_name'))
            self.assertEqual(device.os_version(), self.get_value(fixture, 'os', 'version'))

            # Client properties
            parsed_name = device.client_name()
            name = APPID_TO_NAME.get(parsed_name, parsed_name)
            self.confirm_client_name(fixture, parsed_name=name)
            self.confirm_client_type(fixture, parsed_value=device.client_type())
            self.confirm_version(fixture, parsed_value=device.client_version())

            # Device properties
            self.matches_fixture_or_generic(fixture, key1='device', key2='type', parsed_value=device.device_type())
            self.matches_fixture_or_generic(fixture, key1='device', key2='model', parsed_value=device.device_model())
            self.matches_fixture_or_generic(fixture, key1='device', key2='brand', parsed_value=device.device_brand())


class ParserBaseTest(Base):

    fixture_files = []
    fixture_key = 'client'   # key of fixture dict containing the values to compare
    fields = []
    Parser = None

    def load_fixtures(self):
        fixtures = []
        for ffile in self.fixture_files:
            with open('{}/{}'.format(ROOT, ffile), 'r') as r:
                fixtures.extend(yaml.load(r, SafeLoader))
        return fixtures

    def test_parsing(self):
        if not self.Parser or not self.fields:
            return

        fixtures = self.load_fixtures()

        for fixture in fixtures:
            self.user_agent = fixture.pop('user_agent')
            expect = fixture[self.fixture_key]
            parsed = self.Parser(self.user_agent).parse()
            data = parsed.ua_data

            for field in self.fields:
                self.assertIn(
                    field, data,
                    msg='Error parsing {}. '
                        'Parsed data does not have "{}" key'.format(self.user_agent, field))
                self.assertEqual(
                    str(expect.get(field, '')), str(data.get(field, '')),
                    msg='Error parsing {}. \n'
                        'Field "{}" parsed value "{}" != expected value "{}"'.format(
                        self.user_agent, field, data.get(field, ''), expect.get(field, '')
                    )
                )


class GenericParserTest(ParserBaseTest):
    skipped = []

    def test_skipped_useragents(self):
        for ua in self.skipped:
            parsed = self.Parser(ua).parse()
            self.assertEqual(parsed.ua_data, {})


if __name__ == '__main__':
    unittest.main()
