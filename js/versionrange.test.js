const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const range = require("./versionrange.js");

const cases = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "tests", "fixtures", "ranges.json"), "utf8")
);

test("JS range verdicts match the shared cases", () => {
  for (const item of cases) {
    const got = range.evaluateProductVersion(item.range, item.version).verdict;
    assert.equal(got, item.verdict, `${item.range} @ ${item.version}`);
  }
});

test("milestone 9.0.0.M1 sorts before 9.0.0", () => {
  const milestone = range.parseUserVersion("9.0.0.M1");
  const release = range.parseUserVersion("9.0.0");
  assert.equal(range.cmpVersion(milestone, release), -1);
  assert.equal(range.cmpVersion(range.parseUserVersion("9.0.0.M1"), range.parseUserVersion("9.0.0-M1")), 0);
  assert.equal(range.cmpVersion(range.parseUserVersion("9.0.0.M2"), range.parseUserVersion("9.0.0.M10")), -1);
});

test("aliases do not substring-match neighboring products", () => {
  assert.equal(range.namesMatch("tomcat-catalina", "Apache Tomcat"), true);
  assert.equal(range.namesMatch("Apache Tomcat", "Apache Tomcat Native"), false);
  assert.equal(range.namesMatch("lodash", "lodash.template"), false);
  assert.equal(range.namesMatch("log4j-core", "Apache Log4j2"), true);
  assert.deepEqual(range.productNamesFor("log4j-core"), ["Apache Log4j2"]);
});
