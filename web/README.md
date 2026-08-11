# arabizikit

Transliterate Arabizi (Romanized Arabic) to Arabic script in the browser or
Node, with dialect tagging and ranked candidates. Zero dependencies.

Arabizi is how millions of Arabs text: "ana 3ayz 2akol" means "أنا عايز آكل".
This package turns that back into Arabic script, handles the ambiguity
honestly (2 can be hamza or qaf, ay can be two words or one), tags the
dialect, and returns ranked candidates instead of one guess.

```js
const { transliterate } = require("arabizikit");

const res = transliterate("ana 3ayz 2akol", { topK: 3, withDialect: true });
console.log(res.text);            // أنا عايز آكل
console.log(res.candidates);      // [{ ar: "أنا عايز آكل", score: 0 }, ...]
console.log(res.dialect.dialect); // egyptian
```

## API

- `transliterate(text, options?)` returns `{ text, candidates, dialect, evidence }`
  - `options.topK` number of ranked candidates (default 3)
  - `options.withDialect` include the dialect guess (default false)
  - `options.dialectHint` assume a convention: egyptian, levantine, gulf, maghrebi
- `tokenize(text)` split into space, latin, and other tokens
- `processWord(word, dialectHint?)` the ranked readings for one word

## Browser

The package ships a single file, `arabizikit.js`, which attaches
`window.ArabiziKit`. Load it with a script tag, or bundle it with any
module system.

```html
<script src="arabizikit.js"></script>
<script>
  const res = ArabiziKit.transliterate("shlonak ya 5al");
  console.log(res.text);
</script>
```

Try the live demo: https://arabizi-kit.vercel.app

## Notes

The tables are the single source of truth: this bundle is generated from the
Python package `arabizikit` (github.com/rb2625/arabizi-kit), which adds a
learned layer (dialect classifier, word reading table, language-model
reranking) and an LLM-assisted mode on top of the same engine.

MIT license.
