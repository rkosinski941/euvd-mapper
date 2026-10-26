/*
 * EUVD product_version parser. Keep behavior aligned with
 * euvd_mapper/versionrange.py and tests/fixtures/ranges.json.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.EuvdRange = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  var QUAL_RANK = {
    alpha: 0,
    beta: 1,
    milestone: 2,
    m: 2,
    rc: 3,
    cr: 3,
    preview: 3,
    pre: 3,
    snapshot: 4
  };
  var RELEASE_RANK = 100;
  var TOKEN_SRC = "(?<![A-Za-z0-9])(\\d+(?:\\.\\d+)*\\.[x*]|\\d+(?:\\.\\d+)*[.\\-](?:alpha|beta|milestone|rc|cr|preview|pre|snapshot|m)\\d*|\\d+(?:\\.\\d+)+|\\d+)(?![A-Za-z0-9])";
  var ALIASES = {
    "tomcat": ["Apache Tomcat"],
    "tomcat-catalina": ["Apache Tomcat"],
    "tomcat-embed-core": ["Apache Tomcat"],
    "tomcat-embed-websocket": ["Apache Tomcat"],
    "tomcat-coyote": ["Apache Tomcat"],
    "tomcat-jasper": ["Apache Tomcat"],
    "tomcat-jdbc": ["Apache Tomcat"],
    "tomcat-jni": ["Apache Tomcat"],
    "tomcat-api": ["Apache Tomcat"],
    "tomcat-util": ["Apache Tomcat"],
    "apache tomcat": ["Apache Tomcat"],
    "apache-tomcat": ["Apache Tomcat"],
    "log4j-core": ["Apache Log4j2"],
    "log4j-api": ["Apache Log4j API"],
    "apache log4j2": ["Apache Log4j2"],
    "lodash": ["lodash"],
    "jackson-databind": ["jackson-databind"],
    "django": ["Django"]
  };

  function normalizeName(name) {
    return String(name || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function productNamesFor(name) {
    var key = normalizeName(name);
    if (!key) return [];
    if (ALIASES[key]) return ALIASES[key].slice();
    return [String(name || "").trim().replace(/\s+/g, " ")];
  }

  function namesMatch(queryName, productName) {
    var product = normalizeName(productName);
    if (!product) return false;
    var targets = {};
    productNamesFor(queryName).forEach(function (item) { targets[normalizeName(item)] = true; });
    targets[normalizeName(queryName)] = true;
    return !!targets[product];
  }

  function tokens(text) {
    var re = new RegExp(TOKEN_SRC, "gi");
    var found = [];
    var match;
    while ((match = re.exec(text))) {
      found.push({
        start: match.index,
        end: match.index + match[0].length,
        text: match[1],
        version: parseToken(match[1])
      });
    }
    return found;
  }

  function parseToken(token) {
    var wild = token.match(/^(\d+(?:\.\d+)*)\.[x*]$/i);
    if (wild) {
      return { numbers: wild[1].split(".").map(Number), preRank: null, preNum: 0, wildcard: true };
    }
    var pre = token.match(/^(\d+(?:\.\d+)*)[.\-](alpha|beta|milestone|rc|cr|preview|pre|snapshot|m)(\d*)$/i);
    if (pre) {
      return {
        numbers: pre[1].split(".").map(Number),
        preRank: QUAL_RANK[pre[2].toLowerCase()],
        preNum: pre[3] ? parseInt(pre[3], 10) : 0,
        wildcard: false
      };
    }
    return { numbers: token.split(".").map(Number), preRank: null, preNum: 0, wildcard: false };
  }

  function cmpVersion(left, right) {
    var length = Math.max(left.numbers.length, right.numbers.length);
    for (var i = 0; i < length; i++) {
      var av = i < left.numbers.length ? left.numbers[i] : 0;
      var bv = i < right.numbers.length ? right.numbers[i] : 0;
      if (av !== bv) return av < bv ? -1 : 1;
    }
    var ar = left.preRank == null ? RELEASE_RANK : left.preRank;
    var br = right.preRank == null ? RELEASE_RANK : right.preRank;
    if (ar !== br) return ar < br ? -1 : 1;
    if (left.preNum !== right.preNum) return left.preNum < right.preNum ? -1 : 1;
    return 0;
  }

  function parseUserVersion(text) {
    if (text == null) return null;
    var raw = String(text).trim().replace(/^v(?=\d)/i, "");
    if (!raw) return null;
    var found = tokens(raw);
    if (found.length !== 1) return null;
    if (found[0].text.toLowerCase() !== raw.toLowerCase()) return null;
    if (found[0].version.wildcard) return null;
    return found[0].version;
  }

  function first(text) {
    var found = tokens(text);
    return found.length ? found[0] : null;
  }

  function last(text) {
    var found = tokens(text);
    return found.length ? found[found.length - 1] : null;
  }

  function isLineLabel(left, upper) {
    if (left.wildcard || left.preRank != null) return false;
    return left.numbers.length < upper.numbers.length &&
      upper.numbers.slice(0, left.numbers.length).every(function (n, i) { return n === left.numbers[i]; });
  }

  function branch(prefix, upper) {
    var found = tokens(prefix);
    for (var i = found.length - 1; i >= 0; i--) {
      var token = found[i];
      var numbers = token.version.numbers;
      if (token.version.wildcard || token.version.preRank != null) continue;
      if (numbers.length < upper.numbers.length &&
          upper.numbers.slice(0, numbers.length).every(function (n, idx) { return n === numbers[idx]; })) {
        return numbers;
      }
    }
    return null;
  }

  function cmpOps(clause) {
    var found = [];
    for (var i = 0; i < clause.length; i++) {
      if (clause.startsWith("<=", i) || clause.startsWith(">=", i)) {
        found.push([clause.slice(i, i + 2), i]);
        i += 1;
      } else if (clause[i] === "<" || clause[i] === ">") {
        found.push([clause[i], i]);
      }
    }
    return found;
  }

  function rangeConstraint(lower, upper, lowerInclusive, upperInclusive, branchNums) {
    return {
      lower: lower || null,
      lowerInclusive: lowerInclusive !== false,
      upper: upper || null,
      upperInclusive: upperInclusive !== false,
      exact: null,
      prefix: null,
      branch: branchNums || null
    };
  }

  function parseClause(clause) {
    var between = clause.match(/\bbetween\b/i);
    if (between) {
      var rest = clause.slice(between.index + between[0].length);
      var conj = rest.match(/\band\b/i);
      if (!conj) return null;
      var leftB = first(rest.slice(0, conj.index));
      var rightB = first(rest.slice(conj.index + conj[0].length));
      if (!leftB || !rightB || leftB.version.wildcard || rightB.version.wildcard) return null;
      return [rangeConstraint(leftB.version, rightB.version, true, true)];
    }
    var earlier = clause.match(/\band\s+earlier\b/i);
    if (earlier) {
      var leftE = last(clause.slice(0, earlier.index));
      if (!leftE || leftE.version.wildcard) return null;
      return [rangeConstraint(null, leftE.version, true, true, branch(clause.slice(0, leftE.start), leftE.version))];
    }
    var before = clause.match(/\b(?:prior\s+to|earlier\s+than|before)\b/i);
    if (before) {
      var rightP = first(clause.slice(before.index + before[0].length));
      if (!rightP || rightP.version.wildcard) return null;
      return [rangeConstraint(null, rightP.version, true, false, branch(clause.slice(0, before.index + before[0].length), rightP.version))];
    }
    var wordTo = clause.match(/\bto\b/i);
    if (wordTo) {
      var leftT = last(clause.slice(0, wordTo.index));
      var rightT = first(clause.slice(wordTo.index + wordTo[0].length));
      if (!leftT || !rightT || leftT.version.wildcard || rightT.version.wildcard) return null;
      return [rangeConstraint(leftT.version, rightT.version, true, true)];
    }
    var ops = cmpOps(clause);
    if (ops.length) {
      var op = ops[0][0];
      var index = ops[0][1];
      var left = last(clause.slice(0, index));
      var right = first(clause.slice(index + op.length));
      if (!right || right.version.wildcard) return null;
      if ((op === "<=" || op === ">=") && left && left.version.wildcard) return null;
      if (op === "<=" && left && !isLineLabel(left.version, right.version)) {
        return [rangeConstraint(left.version, right.version, true, true)];
      }
      if (op === "<=") {
        return [rangeConstraint(null, right.version, true, true, branch(clause.slice(0, index), right.version))];
      }
      if (op === "<" && left && !isLineLabel(left.version, right.version)) {
        if (left.version.wildcard) return null;
        return [rangeConstraint(left.version, right.version, true, false)];
      }
      if (op === "<") {
        return [rangeConstraint(null, right.version, true, false, branch(clause.slice(0, index), right.version))];
      }
      if (op === ">=" && !left) return [rangeConstraint(right.version, null, true, true)];
      if (op === ">" && !left) return [rangeConstraint(right.version, null, false, true)];
      return null;
    }
    var found = tokens(clause);
    if (!found.length) return [];
    var specific = found[0];
    found.forEach(function (item) {
      if (item.version.numbers.length > specific.version.numbers.length ||
          (item.version.numbers.length === specific.version.numbers.length && item.start >= specific.start)) {
        specific = item;
      }
    });
    if (specific.version.wildcard) {
      return [{ lower: null, upper: null, exact: null, prefix: specific.version.numbers, branch: null }];
    }
    return [{ lower: null, upper: null, exact: specific.version, prefix: null, branch: null }];
  }

  function parseConstraints(text) {
    if (text == null) return null;
    var raw = String(text).trim();
    if (!raw || ["n/a", "na", "none", "unknown", "unspecified", "-"].indexOf(raw.toLowerCase()) >= 0) return null;
    var cleaned = raw.replace(/\[[^\]]*\]/g, " ").replace(/\u2264/g, " <= ").replace(/\u2265/g, " >= ").replace(/\u2266/g, " <= ");
    var clauses = cleaned.split(",").map(function (part) { return part.trim(); }).filter(Boolean);
    var parsed = [];
    for (var i = 0; i < clauses.length; i++) {
      var piece = parseClause(clauses[i]);
      if (piece == null) return null;
      parsed = parsed.concat(piece);
    }
    return parsed.length ? parsed : null;
  }

  function shares(version, prefix) {
    var padded = version.numbers.slice();
    while (padded.length < prefix.length) padded.push(0);
    return prefix.every(function (n, i) { return padded[i] === n; });
  }

  function contains(constraint, version) {
    if (constraint.exact) return cmpVersion(version, constraint.exact) === 0;
    if (constraint.prefix) return shares(version, constraint.prefix);
    if (constraint.branch && !shares(version, constraint.branch)) return false;
    if (constraint.lower) {
      var low = cmpVersion(version, constraint.lower);
      if (constraint.lowerInclusive) {
        if (low < 0) return false;
      } else if (low <= 0) return false;
    }
    if (constraint.upper) {
      var high = cmpVersion(version, constraint.upper);
      if (constraint.upperInclusive) {
        if (high > 0) return false;
      } else if (high >= 0) return false;
    }
    return !!(constraint.lower || constraint.upper);
  }

  function clip(text) {
    var raw = text == null ? "" : String(text).trim();
    return raw.length <= 180 ? raw : raw.slice(0, 179) + "...";
  }

  function evaluateProductVersion(rangeText, version) {
    var shown = clip(rangeText);
    if (version == null || !String(version).trim()) {
      return { verdict: "unknown", evidence: "no version supplied" };
    }
    var versionText = String(version).trim();
    var target = parseUserVersion(versionText);
    if (!target) {
      return { verdict: "unknown", evidence: "version '" + versionText + "' is not a comparable version" };
    }
    var constraints = parseConstraints(rangeText);
    if (!constraints) {
      return { verdict: "unknown", evidence: "EUVD product_version '" + shown + "' is not a parseable range" };
    }
    for (var i = 0; i < constraints.length; i++) {
      if (contains(constraints[i], target)) {
        return { verdict: "affected", evidence: "EUVD range '" + shown + "' includes " + versionText };
      }
    }
    return { verdict: "not_affected", evidence: "EUVD range '" + shown + "' excludes " + versionText };
  }

  function versionMightMatch(rangeText, version) {
    return evaluateProductVersion(rangeText, version).verdict === "affected";
  }

  return {
    evaluateProductVersion: evaluateProductVersion,
    versionMightMatch: versionMightMatch,
    namesMatch: namesMatch,
    productNamesFor: productNamesFor,
    cmpVersion: cmpVersion,
    parseUserVersion: parseUserVersion
  };
});
