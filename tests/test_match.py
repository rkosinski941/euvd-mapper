import unittest
import urllib.parse

from euvd_mapper.euvd import SEARCH_URL, search_product
from euvd_mapper.match import match_component


def _record(eid, aliases, products, description="", score=None):
    return {
        "id": eid,
        "aliases": "\n".join(aliases) + ("\n" if aliases else ""),
        "description": description,
        "baseScore": score,
        "enisaIdProduct": [
            {
                "product_version": version,
                "product": {"name": name, "vendor": {"name": vendor}},
            }
            for name, version, vendor in products
        ],
    }


def _search(product, items, total=None):
    query = urllib.parse.urlencode({"product": product, "size": 100, "page": 0})
    return SEARCH_URL + "?" + query, {"items": items, "total": total if total is not None else len(items)}


class FakeHttp:
    def __init__(self):
        self.gets = {}
        self.posts = {}

    def get_json(self, url):
        if url not in self.gets:
            raise AssertionError("unexpected GET " + url)
        return self.gets[url]

    def post_json(self, url, body):
        key = (url, body["package"]["purl"], body.get("version"))
        if key not in self.posts:
            raise AssertionError("unexpected POST " + str(key))
        return self.posts[key]


class MatchTest(unittest.TestCase):
    def test_tomcat_euvd_includes_9_0_20_when_osv_does_not_list_it(self):
        http = FakeHttp()
        native = _record(
            "EUVD-NATIVE",
            ["CVE-2000-0001"],
            [("Apache Tomcat Native", "1.2.0 to 1.2.9", "Apache")],
        )
        mixed = _record(
            "EUVD-2022-4051",
            ["CVE-2022-25762", "GHSA-h3ch-5pp2-vh6w"],
            [
                ("Apache Tomcat", "Apache Tomcat 9 9.0.0.M1 to 9.0.20", "Apache Software Foundation"),
                ("Apache Tomcat", "Apache Tomcat 8.5 8.5.0 to 8.5.75", "Apache Software Foundation"),
            ],
        )
        agreed = _record(
            "EUVD-2020-1111",
            ["CVE-2020-9484", "GHSA-344f-f5vg-2jfj"],
            [("Apache Tomcat", "9.0.0.M1 to 9.0.98", "Apache Software Foundation")],
            score=7.0,
        )
        fixed = _record(
            "EUVD-FIXED",
            ["CVE-2019-0001"],
            [("Apache Tomcat", "9.0.0.M1 to 9.0.10", "Apache Software Foundation")],
        )
        url, payload = _search("Apache Tomcat", [native, mixed, agreed, fixed])
        http.gets[url] = payload
        http.gets["https://euvdservices.enisa.europa.eu/api/enisaid?id=CVE-2020-9484"] = agreed
        http.posts[("https://api.osv.dev/v1/query", "pkg:maven/org.apache.tomcat/tomcat-catalina", "9.0.20")] = {
            "vulns": [{"id": "GHSA-344f-f5vg-2jfj", "aliases": ["CVE-2020-9484"]}]
        }
        result = match_component(
            http,
            name="tomcat-catalina",
            purl="pkg:maven/org.apache.tomcat/tomcat-catalina@9.0.20",
        )
        by_id = {item.euvd_id: item for item in result.records}
        self.assertNotIn("EUVD-NATIVE", by_id)
        self.assertEqual(by_id["EUVD-2022-4051"].verdict, "disagree")
        self.assertEqual(by_id["EUVD-2022-4051"].euvd_verdict, "affected")
        self.assertEqual(by_id["EUVD-2022-4051"].match_basis, "euvd-range")
        self.assertIn("did not list", by_id["EUVD-2022-4051"].evidence)
        self.assertEqual(by_id["EUVD-2020-1111"].verdict, "affected")
        self.assertEqual(by_id["EUVD-2020-1111"].cross_check, "agree")
        self.assertEqual(by_id["EUVD-2020-1111"].match_basis, "osv-range")
        self.assertEqual(by_id["EUVD-FIXED"].verdict, "not_affected")
        self.assertEqual(result.verdict, "affected")

    def test_malformed_log4shell_range_uses_osv_and_does_not_invent_a_bound(self):
        http = FakeHttp()
        record = _record(
            "EUVD-2021-34768",
            ["CVE-2021-44228"],
            [("Apache Log4j2", "2.0-beta9 <log4j-core*", "Apache Software Foundation")],
            description="Apache Log4j2 2.0-beta9 through 2.15.0",
            score=10,
        )
        url, payload = _search("Apache Log4j2", [record])
        http.gets[url] = payload
        http.gets["https://euvdservices.enisa.europa.eu/api/enisaid?id=CVE-2021-44228"] = record
        http.posts[("https://api.osv.dev/v1/query", "pkg:maven/org.apache.logging.log4j/log4j-core", "2.14.1")] = {
            "vulns": [{"id": "GHSA-jfh8-c2jp-5v3q", "aliases": ["CVE-2021-44228"]}]
        }
        result = match_component(http, purl="pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1")
        hit = result.records[0]
        self.assertEqual(hit.euvd_id, "EUVD-2021-34768")
        self.assertEqual(hit.euvd_verdict, "unknown")
        self.assertEqual(hit.verdict, "affected")
        self.assertEqual(hit.match_basis, "osv-range")
        self.assertEqual(hit.cross_check, "osv_only")
        self.assertIn("not a parseable range", hit.evidence)
        self.assertEqual(hit.severity, "critical")

    def test_exact_product_version_that_contradicts_the_description_is_unknown(self):
        http = FakeHttp()
        record = _record(
            "EUVD-2020-0440",
            ["CVE-2019-14893"],
            [
                ("jackson-databind", "2.9.10", "n/a"),
                ("jackson-databind", "2.10.0", "n/a"),
            ],
            description="A flaw was discovered in all versions before 2.9.10 and 2.10.0",
            score=7.5,
        )
        url, payload = _search("jackson-databind", [record])
        http.gets[url] = payload
        result = match_component(http, name="jackson-databind", version="2.9.10")
        hit = result.records[0]
        self.assertEqual(hit.verdict, "unknown")
        self.assertNotEqual(hit.verdict, "affected")
        self.assertIn("contradicts the description", hit.evidence)

    def test_fixed_version_is_not_affected_and_garbage_version_is_unknown(self):
        http = FakeHttp()
        record = _record(
            "EUVD-2022-4051",
            ["CVE-2022-25762"],
            [("Apache Tomcat", "Apache Tomcat 9 9.0.0.M1 to 9.0.20", "Apache")],
        )
        url, payload = _search("Apache Tomcat", [record])
        http.gets[url] = payload
        fixed = match_component(http, name="Apache Tomcat", version="9.0.21")
        self.assertEqual(fixed.records[0].verdict, "not_affected")
        self.assertEqual(fixed.verdict, "not_affected")
        unknown = match_component(http, name="Apache Tomcat", version="latest")
        self.assertEqual(unknown.records[0].verdict, "unknown")
        self.assertEqual(unknown.verdict, "unknown")
        self.assertNotEqual(unknown.records[0].verdict, "affected")
        missing = match_component(http, name="Apache Tomcat")
        self.assertEqual(missing.records[0].verdict, "unknown")
        self.assertEqual(missing.records[0].match_basis, "name-only")

    def test_lodash_prior_to_agrees_with_osv(self):
        http = FakeHttp()
        record = _record(
            "EUVD-2021-0912",
            ["CVE-2021-23337", "GHSA-35jh-r3h4-6jhm"],
            [("lodash", "prior to 4.17.21", "lodash")],
            score=7.2,
        )
        url, payload = _search("lodash", [record])
        http.gets[url] = payload
        http.gets["https://euvdservices.enisa.europa.eu/api/enisaid?id=CVE-2021-23337"] = record
        http.posts[("https://api.osv.dev/v1/query", "pkg:npm/lodash", "4.17.15")] = {
            "vulns": [{"id": "GHSA-35jh-r3h4-6jhm", "aliases": ["CVE-2021-23337"]}]
        }
        result = match_component(http, purl="pkg:npm/lodash@4.17.15")
        hit = {item.euvd_id: item for item in result.records}["EUVD-2021-0912"]
        self.assertEqual(hit.verdict, "affected")
        self.assertEqual(hit.cross_check, "agree")
        self.assertEqual(hit.match_basis, "osv-range")


class PagingTest(unittest.TestCase):
    def test_search_walks_pages_until_short_and_dedupes(self):
        class Pages:
            def get_json(self, url):
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                page = int(parsed["page"][0])
                if page == 0:
                    items = [{"id": f"EUVD-{i}"} for i in range(100)]
                elif page == 1:
                    items = [{"id": "EUVD-0"}, {"id": "EUVD-100"}]
                else:
                    items = []
                return {"items": items, "total": 101}

        items, total = search_product(Pages(), "Apache Tomcat")
        self.assertEqual(total, 101)
        self.assertEqual(len(items), 101)
        self.assertEqual(items[-1]["id"], "EUVD-100")


if __name__ == "__main__":
    unittest.main()
