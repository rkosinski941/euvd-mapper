import unittest

from euvd_mapper.aliases import names_match, product_names_for
from euvd_mapper.purl import parse_purl
from euvd_mapper.versionrange import cmp_version, evaluate_product_version, parse_user_version


def verdict(range_text, version):
    return evaluate_product_version(range_text, version).verdict


class OrderingTest(unittest.TestCase):
    def cmp(self, left, right):
        return cmp_version(parse_user_version(left), parse_user_version(right))

    def test_milestone_and_rc_sort_before_the_release(self):
        self.assertLess(self.cmp("9.0.0.M1", "9.0.0"), 0)
        self.assertLess(self.cmp("9.0.0-M1", "9.0.0"), 0)
        self.assertEqual(self.cmp("9.0.0.M1", "9.0.0-M1"), 0)
        self.assertLess(self.cmp("9.0.0.M1", "9.0.0.M2"), 0)
        self.assertLess(self.cmp("9.0.0.M2", "9.0.0.M10"), 0)
        self.assertLess(self.cmp("9.0.0.M10", "9.0.0"), 0)
        self.assertLess(self.cmp("10.0.0-M1", "10.0.0-M10"), 0)
        self.assertLess(self.cmp("10.0.0-M10", "10.0.0"), 0)
        self.assertLess(self.cmp("8.0.0.RC1", "8.0.0"), 0)
        self.assertLess(self.cmp("8.0.0.M1", "8.0.0.RC1"), 0)
        self.assertLess(self.cmp("2.0-alpha1", "2.0-beta9"), 0)
        self.assertLess(self.cmp("2.0-beta9", "2.0"), 0)
        self.assertLess(self.cmp("2.0", "2.8.1"), 0)

    def test_missing_components_pad_with_zero(self):
        self.assertEqual(self.cmp("8.5", "8.5.0"), 0)
        self.assertLess(self.cmp("9", "9.0.20"), 0)


class RangeTest(unittest.TestCase):
    def test_tomcat_to_range_includes_the_end_and_milestones(self):
        text = "Apache Tomcat 9 9.0.0.M1 to 9.0.20"
        self.assertEqual(verdict(text, "9.0.20"), "affected")
        self.assertEqual(verdict(text, "9.0.0.M1"), "affected")
        self.assertEqual(verdict(text, "9.0.0-M1"), "affected")
        self.assertEqual(verdict(text, "9.0.0"), "affected")
        self.assertEqual(verdict(text, "9.0.21"), "not_affected")
        self.assertEqual(verdict(text, "8.5.50"), "not_affected")

    def test_hyphen_milestone_to_range(self):
        text = "Apache Tomcat 10 10.0.0-M1 to 10.0.2"
        self.assertEqual(verdict(text, "10.0.0-M1"), "affected")
        self.assertEqual(verdict(text, "10.0.0"), "affected")
        self.assertEqual(verdict(text, "10.0.2"), "affected")
        self.assertEqual(verdict(text, "10.0.3"), "not_affected")

    def test_leq_separator_is_inclusive(self):
        text = "8.5.85 \u22648.5.93"
        self.assertEqual(verdict(text, "8.5.85"), "affected")
        self.assertEqual(verdict(text, "8.5.93"), "affected")
        self.assertEqual(verdict(text, "8.5.84"), "not_affected")
        self.assertEqual(verdict(text, "8.5.94"), "not_affected")

    def test_upper_bound_keeps_the_product_line(self):
        text = "Apache Tomcat 9 <9.0.42"
        self.assertEqual(verdict(text, "9.0.0.M1"), "affected")
        self.assertEqual(verdict(text, "9.0.41"), "affected")
        self.assertEqual(verdict(text, "9.0.42"), "not_affected")
        self.assertEqual(verdict(text, "8.5.50"), "not_affected")
        self.assertEqual(verdict(text, "10.0.1"), "not_affected")

        line = "Apache Tomcat 8.5 <8.5.62"
        self.assertEqual(verdict(line, "8.5.0"), "affected")
        self.assertEqual(verdict(line, "8.5.61"), "affected")
        self.assertEqual(verdict(line, "8.5.62"), "not_affected")
        self.assertEqual(verdict(line, "8.0.50"), "not_affected")
        self.assertEqual(verdict(line, "9.0.0"), "not_affected")

    def test_two_sided_less_than_and_fileupload(self):
        self.assertEqual(verdict("0 <1.5", "1.4"), "affected")
        self.assertEqual(verdict("0 <1.5", "0"), "affected")
        self.assertEqual(verdict("0 <1.5", "1.5"), "not_affected")
        self.assertEqual(verdict("0 <1.5", "2.0"), "not_affected")
        self.assertEqual(verdict("2.14.0 <2.25.4", "2.14.0"), "affected")
        self.assertEqual(verdict("2.14.0 <2.25.4", "2.14.1"), "affected")
        self.assertEqual(verdict("2.14.0 <2.25.4", "2.25.4"), "not_affected")
        self.assertEqual(verdict("2.14.0 <2.25.4", "2.13.0"), "not_affected")

    def test_artifact_prefix_upper_bound(self):
        self.assertEqual(verdict("log4j-core <2.17.1", "2.14.1"), "affected")
        self.assertEqual(verdict("log4j-core <2.17.1", "2.17.0"), "affected")
        self.assertEqual(verdict("log4j-core <2.17.1", "2.17.1"), "not_affected")

    def test_prior_to_and_before_are_exclusive(self):
        self.assertEqual(verdict("prior to 4.17.21", "4.17.15"), "affected")
        self.assertEqual(verdict("prior to 4.17.21", "4.17.21"), "not_affected")
        self.assertEqual(verdict("versions prior to 4.17.21", "4.17.20"), "affected")
        self.assertEqual(verdict("Versions before 4.17.5", "4.17.4"), "affected")
        self.assertEqual(verdict("Versions before 4.17.5", "4.17.5"), "not_affected")
        self.assertEqual(verdict("before 2.6.7.1", "2.6.7"), "affected")
        self.assertEqual(verdict("before 2.6.7.1", "2.6.7.1"), "not_affected")

    def test_bracket_annotation_is_not_a_second_range(self):
        text = "<4.17.11 [fixed: 4.7.11]"
        self.assertEqual(verdict(text, "4.17.10"), "affected")
        self.assertEqual(verdict(text, "4.17.11"), "not_affected")

    def test_comma_list_is_a_union(self):
        text = "10.0.0-M1 to 10.0.0-M6, 9.0.0.M5 to 9.0.36, 8.5.1 to 8.5.56"
        self.assertEqual(verdict(text, "10.0.0-M3"), "affected")
        self.assertEqual(verdict(text, "10.0.0-M7"), "not_affected")
        self.assertEqual(verdict(text, "10.0.0"), "not_affected")
        self.assertEqual(verdict(text, "9.0.20"), "affected")
        self.assertEqual(verdict(text, "9.0.0.M1"), "not_affected")
        self.assertEqual(verdict(text, "8.5.56"), "affected")
        self.assertEqual(verdict(text, "8.5.57"), "not_affected")
        self.assertEqual(verdict(text, "7.0.50"), "not_affected")

    def test_between_and_exact_and_wildcard(self):
        text = "All versions between 2.0-alpha1 and 2.8.1"
        self.assertEqual(verdict(text, "2.0-alpha1"), "affected")
        self.assertEqual(verdict(text, "2.0-beta9"), "affected")
        self.assertEqual(verdict(text, "2.0"), "affected")
        self.assertEqual(verdict(text, "2.8.1"), "affected")
        self.assertEqual(verdict(text, "2.8.2"), "not_affected")
        self.assertEqual(verdict("log4j-core 2.13.0", "2.13.0"), "affected")
        self.assertEqual(verdict("log4j-core 2.13.0", "2.13.1"), "not_affected")
        self.assertEqual(verdict("2.9.10", "2.9.10"), "affected")
        self.assertEqual(verdict("2.9.10", "2.9.9"), "not_affected")
        self.assertEqual(verdict("11.0.0-M1", "11.0.0-M1"), "affected")
        self.assertEqual(verdict("11.0.0-M1", "11.0.0"), "not_affected")
        self.assertEqual(verdict("Apache Log4j 1.2 1.2.x", "1.2.17"), "affected")
        self.assertEqual(verdict("Apache Log4j 1.2 1.2.x", "1.3.0"), "not_affected")

    def test_malformed_and_incomparable_stay_unknown(self):
        self.assertEqual(verdict("2.0-beta9 <log4j-core*", "2.14.1"), "unknown")
        self.assertEqual(verdict("n/a", "2.14.1"), "unknown")
        self.assertEqual(verdict("Apache Tomcat 9 9.0.0.M1 to 9.0.20", "latest"), "unknown")
        self.assertEqual(verdict("Apache Tomcat 9 9.0.0.M1 to 9.0.20", ""), "unknown")
        self.assertEqual(verdict("Apache Tomcat 9 9.0.0.M1 to 9.0.20", None), "unknown")
        result = evaluate_product_version("2.0-beta9 <log4j-core*", "2.14.1")
        self.assertIn("not a parseable range", result.evidence)
        self.assertNotEqual(result.verdict, "affected")

    def test_milestone_upper_bound_on_a_major_line(self):
        text = "Apache Tomcat 10 <10.0.0-M10"
        self.assertEqual(verdict(text, "10.0.0-M5"), "affected")
        self.assertEqual(verdict(text, "10.0.0-M10"), "not_affected")
        self.assertEqual(verdict(text, "10.0.0"), "not_affected")
        self.assertEqual(verdict(text, "9.0.20"), "not_affected")


class AliasAndPurlTest(unittest.TestCase):
    def test_aliases_are_exact(self):
        self.assertEqual(product_names_for("tomcat-catalina"), ("Apache Tomcat",))
        self.assertEqual(product_names_for("log4j-core"), ("Apache Log4j2",))
        self.assertTrue(names_match("tomcat-catalina", "Apache Tomcat"))
        self.assertTrue(names_match("Apache Tomcat", "Apache Tomcat"))
        self.assertFalse(names_match("Apache Tomcat", "Apache Tomcat Native"))
        self.assertFalse(names_match("lodash", "lodash.template"))
        self.assertFalse(names_match("lodash", "lodash-es"))
        self.assertTrue(names_match("lodash", "lodash"))
        self.assertTrue(names_match("jackson-databind", "jackson-databind"))
        self.assertTrue(names_match("django", "Django"))

    def test_purl_splits_version_off_for_osv(self):
        parsed = parse_purl("pkg:maven/org.apache.tomcat/tomcat-catalina@9.0.20")
        self.assertEqual(parsed.type, "maven")
        self.assertEqual(parsed.namespace, "org.apache.tomcat")
        self.assertEqual(parsed.name, "tomcat-catalina")
        self.assertEqual(parsed.version, "9.0.20")
        self.assertEqual(
            parsed.osv_query(),
            {
                "package": {"purl": "pkg:maven/org.apache.tomcat/tomcat-catalina"},
                "version": "9.0.20",
            },
        )
        npm = parse_purl("pkg:npm/lodash@4.17.15")
        self.assertEqual(npm.name, "lodash")
        self.assertIsNone(npm.namespace)
        pypi = parse_purl("pkg:pypi/django@3.2.0")
        self.assertEqual(pypi.osv_query()["version"], "3.2.0")
        self.assertIsNone(parse_purl("not a purl"))


if __name__ == "__main__":
    unittest.main()
