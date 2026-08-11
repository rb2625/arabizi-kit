/* ArabiziKit browser engine — mirrors src/arabizikit/transliterate.py.
 *
 * This file is concatenated after the data tables (PHONEMES, LEXICON) by
 * scripts/build_web.py to produce web/arabizikit.js. Keep the algorithm in
 * lock-step with the Python implementation; the tables are the single source
 * of truth and are embedded verbatim from src/arabizikit/data/.
 */
(function (global) {
  "use strict";

  const ARTICLES = new Set(["el", "al", "il", "l"]);
  const CONTRACTIONS = { "3al": { prefix: "على ال", fallback: "على" } };
  const CONJ = { "w": "و" };
  const PREPOSITIONS = new Set(["ب", "ف", "ك", "ل", "د", "و"]);
  const DIALECTS = ["gulf", "egyptian", "levantine", "maghrebi"];
  const PATTERN_RULES = [
    ["maghrebi", /\b(wesh|wacha|kifash|3afak|bzzaf|daba|sh7al|bghit|mzyan)\b/i],
    ["gulf", /\b(shlonak|shlonik|shakhbarak|2ol|2ool|wayed|zayn|walaw|shway)\b/i],
    ["levantine", /\b(shu|keefak|keefik|beddi|biddi|mafi|kolshi|mneeh|mnih|kteer|keteer)\b/i],
    ["egyptian", /\b(ezayak|ezayek|3ayz|3ayza|ayz|awi|mesh|mish|kwayes|kwayis|eih|aywa|keda|3ashan)\b/i],
  ];

  const DIGRAPHS = Object.keys(PHONEMES.digraphs).sort((a, b) => b.length - a.length);
  const DIGRAPH_MAP = PHONEMES.digraphs;
  const DIGRAPH_ALTS = PHONEMES.digraph_alternatives || {};
  const DIGITS = PHONEMES.digits;
  const LETTERS = PHONEMES.letters;
  const CASE_RULES = PHONEMES.case_rules || {};
  const CONTEXT = {};
  for (const r of PHONEMES.context_rules) CONTEXT[r.id] = r;
  const BAD = PHONEMES.bad_sequences;
  const HAMZA = PHONEMES.hamza_seating;

  function tokenize(text) {
    const tokens = [];
    for (const chunk of text.split(/(\s+)/)) {
      if (!chunk) continue;
      if (/^\s+$/.test(chunk)) { tokens.push({ kind: "space", raw: chunk }); continue; }
      const re = /[A-Za-z0-9'’]+|[^\sA-Za-z0-9'’]+/g;
      let m;
      while ((m = re.exec(chunk))) {
        const piece = m[0];
        tokens.push({ kind: /^[A-Za-z0-9'’]+$/.test(piece) ? "latin" : "other", raw: piece });
      }
    }
    return tokens;
  }

  function scanWord(word, dialectHint) {
    const segments = [];
    let i = 0;
    const n = word.length;
    const low = word.toLowerCase();
    const hint = dialectHint ? String(dialectHint).toLowerCase() : null;
    while (i < n) {
      const ch = low[i];
      const orig = word[i];

      if ("ae".indexOf(ch) !== -1 && i + 1 < n && low[i + 1] === "y" &&
          (i + 2 >= n || low[i + 2] !== "y")) {
        segments.push({ options: ["اي", "ي"] });
        i += 2;
        continue;
      }
      if ("98".indexOf(ch) !== -1 && i + 1 < n && "'’".indexOf(word[i + 1]) !== -1) {
        segments.push({ options: [ch === "9" ? "ض" : "غ"] });
        i += 2;
        continue;
      }
      const doubled = i + 1 < n && low[i + 1] === ch && "aeiou".indexOf(ch) === -1;

      let digraph = null;
      for (const d of DIGRAPHS) {
        if (low.startsWith(d, i)) { digraph = d; break; }
      }
      if (digraph) {
        const opts = [DIGRAPH_MAP[digraph]];
        for (const alt of DIGRAPH_ALTS[digraph] || []) {
          if (alt !== opts[0]) opts.push(alt);
        }
        segments.push({ options: opts });
        i += digraph.length;
        continue;
      }
      if (ch in DIGITS) {
        let primary = DIGITS[ch].primary;
        let alts = (DIGITS[ch].alternatives || []).slice();
        if (hint && DIGITS[ch].dialect_variants && DIGITS[ch].dialect_variants[hint]) {
          const variant = DIGITS[ch].dialect_variants[hint];
          primary = variant.primary;
          alts = (variant.alternatives || []).slice();
        }
        if (ch === "2") {
          const prevOut = segments.length ? segments[segments.length - 1].options[0] : "";
          if (i === n - 1 && ["ا", "و", "ي", ""].indexOf(prevOut) !== -1) {
            primary = "ق"; alts = alts.filter((a) => a !== "ق");
          } else if (i === 0 && n > 1 && "aeiou".indexOf(low[1]) === -1) {
            primary = "ق"; alts = ["ا"];
          }
        }
        const options = [primary].concat(alts.filter((a) => a !== primary));
        segments.push({ options });
        i += doubled ? 2 : 1;
        continue;
      }
      if (ch in LETTERS) {
        let primary = LETTERS[ch].primary;
        let alts = (LETTERS[ch].alternatives || []).slice();
        if (orig !== ch) {
          const caseRule = CASE_RULES[orig];
          if (caseRule) {
            primary = caseRule.primary;
            alts = (caseRule.alternatives || []).slice();
          }
        }
        if (ch === "a" && i === n - 1 && CONTEXT.final_a_taa_marbuta) {
          primary = CONTEXT.final_a_taa_marbuta.primary;
          alts = (CONTEXT.final_a_taa_marbuta.alternatives || []).slice();
        }
        if (ch === "i" && i === n - 1) { primary = "ي"; alts = alts.filter((a) => a !== "ي"); }
        let options = [primary].concat(alts.filter((a) => a !== primary));
        if (doubled) {
          if (hint === "maghrebi") {
            options = [options[0], options[0] + options[0]].concat(options.slice(1));
            if (i === 0) {
              options = ["ال" + options[0]].concat(options);
            } else if (segments.length && segments[segments.length - 1].options[0].length === 1 &&
                       PREPOSITIONS.has(segments[segments.length - 1].options[0])) {
              options = options.slice(0, 1).concat(["ال" + options[0]]).concat(options.slice(1));
            }
          } else {
            options = [options[0] + options[0]].concat(options);
          }
        }
        segments.push({ options });
        i += doubled ? 2 : 1;
        continue;
      }
      segments.push({ options: [ch] });
      i += 1;
    }
    return segments;
  }

  function seatHamza(s) {
    const chars = Array.from(s);
    const out = [];
    let i = 0;
    const n = chars.length;
    while (i < n) {
      const ch = chars[i];
      if (ch !== "ء") { out.push(ch); i += 1; continue; }
      const prev = out.length ? out[out.length - 1] : null;
      const nxt = i + 1 < n ? chars[i + 1] : null;
      if (prev === null) {
        out.push(nxt === "ي" ? HAMZA.word_initial.before_ya : HAMZA.word_initial.default);
        i += 1;
      } else if (prev === "و") {
        out[out.length - 1] = HAMZA.after_waaw; i += 1;
      } else if (prev === "ي") {
        out[out.length - 1] = HAMZA.after_ya; i += 1;
      } else if (prev === "ا") {
        out[out.length - 1] = HAMZA.after_alif; i += (nxt === "ا" ? 2 : 1);
      } else if (nxt === "ا") {
        out.push(HAMZA.after_alif); i += 2;
      } else {
        out.push(HAMZA.else); i += 1;
      }
    }
    return out.join("");
  }

  function ruleCandidates(word, maxCandidates, dialectHint) {
    maxCandidates = maxCandidates || 8;
    const segments = scanWord(word, dialectHint);
    let results = [""];
    for (const seg of segments) {
      let opts = seg.options;
      if (results.length * opts.length > maxCandidates * 4) opts = opts.slice(0, 1);
      const next = [];
      for (const r of results) for (const o of opts) next.push(r + o);
      results = next;
    }
    const seen = new Set();
    const scored = [];
    results.map(seatHamza).forEach((ar, idx) => {
      if (seen.has(ar)) return;
      seen.add(ar);
      let penalty = 0;
      for (const seq of BAD) if (ar.indexOf(seq) !== -1) penalty += 2;
      scored.push({ ar, score: penalty + idx * 1e-6 });
    });
    scored.sort((a, b) => a.score - b.score);
    return scored.slice(0, Math.max(maxCandidates, 1));
  }

  function processWord(word, dialectHint) {
    const low = word.toLowerCase();
    if (CONJ[low] !== undefined) return { kind: "conj", raw: low, attach: CONJ[low] };
    if (ARTICLES.has(low)) return { kind: "article", raw: low };
    if (CONTRACTIONS[low]) return { kind: "contraction", raw: low, prefix: CONTRACTIONS[low].prefix, fallback: CONTRACTIONS[low].fallback };
    const entry = LEXICON[low];
    if (entry) {
      return {
        kind: "word", raw: low,
        candidates: [{ ar: entry.ar, score: 0.0 }],
        evidence: [{ arabizi: low, ar: entry.ar, dialect: entry.dialect }],
      };
    }
    return { kind: "word", raw: low, candidates: ruleCandidates(word, undefined, dialectHint), evidence: [] };
  }

  function attachPass(words) {
    const out = [];
    let i = 0;
    while (i < words.length) {
      const w = words[i];
      if (w.kind === "article" || w.kind === "conj" || w.kind === "contraction") {
        let prefix, fallback;
        if (w.kind === "article") { prefix = "ال"; fallback = null; }
        else if (w.kind === "conj") { prefix = w.attach; fallback = "و"; }
        else { prefix = w.prefix; fallback = w.fallback; }
        let j = i + 1;
        while (j < words.length && words[j].kind === "space") j += 1;
        if (j < words.length && words[j].kind === "word") {
          words[j].candidates = words[j].candidates.map((c) => ({ ar: prefix + c.ar, score: c.score }));
          i = j;
          continue;
        }
        out.push({ kind: "word", raw: w.raw, candidates: [{ ar: fallback || prefix, score: 0.0 }], evidence: [] });
        i += 1;
        continue;
      }
      out.push(w);
      i += 1;
    }
    return out;
  }

  function sentenceCandidates(words, topK) {
    const wordTokens = words.filter((w) => w.kind === "word");
    let combos = [{ parts: [], score: 0.0 }];
    for (const w of wordTokens) {
      const cands = w.candidates.slice(0, topK);
      const next = [];
      for (const c of combos) for (const cand of cands) {
        next.push({ parts: c.parts.concat(cand.ar), score: c.score + cand.score });
      }
      combos = next;
      if (combos.length > topK * 6) {
        combos = combos.slice().sort((a, b) => a.score - b.score).slice(0, topK * 6);
      }
    }
    if (!wordTokens.length) return [];
    const seen = new Set();
    const out = [];
    combos.slice().sort((a, b) => a.score - b.score).forEach((c) => {
      const sentence = c.parts.join(" ");
      if (seen.has(sentence)) return;
      seen.add(sentence);
      out.push({ ar: sentence, score: Math.round(c.score * 1e6) / 1e6 });
    });
    return out.slice(0, Math.max(topK, 1));
  }

  function guessDialect(evidence) {
    const counts = {};
    const matched = [];
    for (const item of evidence) {
      const d = item.dialect;
      if (DIALECTS.indexOf(d) === -1) continue;
      counts[d] = (counts[d] || 0) + 1;
      matched.push(item);
    }
    if (!Object.keys(counts).length) return { dialect: "unknown", confidence: 0.0, evidence: [] };
    let top = null;
    for (const d of Object.keys(counts)) {
      if (top === null || counts[d] > counts[top]) top = d;
    }
    const total = Object.keys(counts).reduce((s, d) => s + counts[d], 0);
    return { dialect: top, confidence: Math.round((counts[top] / total) * 100) / 100, evidence: matched };
  }

  function transliterate(text, opts) {
    opts = opts || {};
    const topK = opts.topK || 1;
    const dialectHint = opts.dialectHint || null;
    const words = attachPass(tokenize(text).map((t) =>
      t.kind === "latin" ? processWord(t.raw, dialectHint) : t
    ));

    const parts = [];
    const evidence = [];
    for (const w of words) {
      if (w.kind === "space" || w.kind === "other") { parts.push(w.raw); continue; }
      if (w.candidates.length) {
        parts.push(w.candidates[0].ar);
        for (const e of (w.evidence || [])) evidence.push(e);
      }
    }
    const textOut = parts.join("");
    const candidates = sentenceCandidates(words, topK);

    let dialect = null;
    if (opts.withDialect) {
      dialect = guessDialect(evidence);
      for (const [d, re] of PATTERN_RULES) {
        if (re.test(text) && (dialect.dialect === "unknown" || dialect.confidence < 0.5)) {
          dialect = { dialect: d, confidence: 0.0, evidence: [] };
          break;
        }
      }
    }
    return { text: textOut, candidates, dialect, evidence };
  }

  global.ArabiziKit = { transliterate, tokenize, processWord };
})(typeof window !== "undefined" ? window : globalThis);
